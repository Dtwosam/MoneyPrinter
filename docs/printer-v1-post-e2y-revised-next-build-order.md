# Printer V1 Post-E2Y Revised Next Build Order

## 1. Status

PROPOSED ONLY. NOT ACTIVE.

This document is a revised next-build-order proposal after:

- E2W-C - 5m support-proof semantics hardening
- E2X - read-only 15m clean-memory eligibility review
- E2Y - read-only 15m candidate set gate
- Post-E2Y roadmap drift checkpoint

This document does not replace the active source-of-truth stack.

This document does not become active unless the operator explicitly adopts it in a separate adoption checkpoint commit/tag.

This document is subordinate to:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-post-lane10-architecture-review.md`
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`
- `docs/printer-v1-post-e2y-roadmap-drift-checkpoint.md`

If this document conflicts with the active Post-RC Build Order, Clean Master Spec, or AGENTS.md, the active source-of-truth wins.

## 2. Why This Revision Exists

The earlier Post-Lane-10 Proposed Next Build Order was written before E2W-C, E2X, and E2Y existed.

After E2W-C/E2X/E2Y, the repo has stronger pre-creation guardrails:

- E2W-C fixed 5m support-proof semantics.
- E2X reviews 15m clean-memory eligibility without creating memory.
- E2Y validates the 15m candidate set as a group without creating memory.
- The Post-E2Y checkpoint paused implementation before roadmap drift.

This revised proposal updates the next-build-order path so future work does not ignore those anchors or continue inventing implementation lanes without operator adoption.

## 3. Current Anchors

Latest checkpoint anchor:

- Commit: `df81088 Add Post-E2Y roadmap drift checkpoint`
- Tag: `printer-v1-post-lane10-post-e2y-roadmap-drift-checkpoint`

Recent safety anchors:

- E2W-C commit: `db6a225 Harden Lane E2W support proof semantics`
- E2W-C tag: `printer-v1-post-lane10-lane-e2wc-support-proof-semantics`
- E2X commit: `ec0285f Add Lane E2X clean-memory eligibility review`
- E2X tag: `printer-v1-post-lane10-lane-e2x-clean-memory-eligibility-review`
- E2Y commit: `33b527f Add Lane E2Y candidate set gate`
- E2Y tag: `printer-v1-post-lane10-lane-e2y-candidate-set-gate`

## 4. Hard Locks Across This Revised Proposal

The following remain locked across every proposed lane:

- live trading
- wallet connection
- private keys
- signing
- real fund movement
- paid API dependency
- scoring, ranking, confidence percentages, weighted decisions
- embeddings/vectors unless separately approved outside V1
- Source Governor bypass
- Central Scheduler bypass
- unbounded runtime
- dirty-memory retrieval
- dirty-memory decisions
- 5m main outcome memory
- 5m-only retrieval unlock
- 5m-only paper decision unlock
- BUY unlock
- SELL/HOLD unlock
- paper positions
- trade events
- paper trade audits
- PnL

If any lane appears to require one of these actions, stop and report.

## 5. Current Proven State

E2W-C proved:

- dirty/audit-only 5m rows no longer prove repeated 5m support
- only valid linked 5m support rows count as repeated 5m support
- real proof: `dirty_5m_count=2`, `valid_linked_5m_count=0`, `repeated_5m_support_proof=false`

E2X proved:

- latest eligible 15m rows can be reviewed without creation
- real proof: `review_candidate_count=5`
- real proof: `legacy_clean_memory_label_count=3`
- real proof: `clean_memory_creation_ready=false`
- real proof: `clean_memory_rows_created=0`
- real proof: `retrieval_activated=false`
- real proof: `paper_decisions_created=0`
- real proof: `buy_enabled=false`

E2Y proved:

- candidate set ids: `[29, 28, 27, 26, 25]`
- snapshot ids: `[91, 92, 93, 94, 95]`
- all candidates are same token/pair `13/13`
- all candidates are `WINDOW_15M`
- all candidates are `WINDOW_CLOSED`
- all candidates are `CLEAN_DATA`
- all candidates are `PARTIAL_MEMORY`
- all candidates are E2Q-audited
- no candidate is dirty or `do_not_train`
- no candidate has a `CLEAN_MEMORY` label
- `set_gate_passed=true`
- no clean memory was created

## 6. Revised Direction

The next direction is not retrieval, paper decisions, BUY, positions, or PnL.

The next direction is:

1. adopt this revised roadmap if operator agrees;
2. inspect clean-memory write target/schema before any write;
3. define exact creation rules for one conservative 15m clean-memory creation boundary;
4. implement creation only after operator approval;
5. keep retrieval and paper decisions locked after creation;
6. only later return to retrieval expansion after enough clean memories exist.

The first goal is not trading.

The first goal is proving that Printer can create clean memory without polluting the DB.

## 7. Revised Lane A - Post-E2Y Revised Roadmap Adoption Checkpoint

Type: documentation only

Operator approval required: yes

Writes allowed:

- documentation only

Allowed:

- compare this revised proposal against active source-of-truth docs
- verify E2W-C/E2X/E2Y anchors
- confirm whether this document becomes the active post-E2Y roadmap extension
- create adoption note if accepted

Not allowed:

- code
- migrations
- DB writes
- source fetching
- scheduler runtime
- memory creation
- retrieval activation
- paper decisions
- BUY, SELL, HOLD
- paper positions
- trade events
- audits
- PnL

Acceptance gate:

- operator explicitly adopts this revised proposal, or requests edits
- adoption commit/tag exists if adopted
- active roadmap stack is updated only by documentation
- implementation remains paused until adoption is complete

## 8. Revised Lane B - Clean-Memory Write Target and Schema Review

Type: read-only review

Operator approval required: yes

Goal:

Before any clean-memory creation, inspect the exact write target, schema expectations, duplicate/idempotency rules, and current DB state.

Allowed:

- read-only schema inspection
- table/column inspection
- existing clean-memory label review
- `printer_memories` existence check
- `printer_memory_windows` clean candidate review
- duplicate/idempotency review
- report-only command if needed
- tests only if a report module is created

Not allowed:

- DB mutation
- migrations
- memory creation
- retrieval activation
- paper decisions
- BUY, SELL, HOLD
- positions
- PnL
- source fetching
- scheduler runtime

Acceptance gate:

- exact clean-memory write target is known
- required fields are known
- duplicate/idempotency rule is known
- legacy `CLEAN_MEMORY` labels are not confused with actual clean-memory rows
- `printer_memories` table absence/presence is explicitly handled
- no writes occurred

## 9. Revised Lane C - Clean-Memory Creation Boundary Design

Type: documentation and tests-first design

Operator approval required: yes

Goal:

Define the smallest safe clean-memory creation boundary before implementation.

Allowed:

- design document
- strict checklist
- fixture tests for eligibility rules
- no-write dry-run report
- idempotency rule definition
- dirty-memory block definition
- 5m-support-only block definition
- operator approval gate

Not allowed:

- DB mutation
- persistent clean-memory creation
- retrieval activation
- paper decisions
- BUY, SELL, HOLD
- positions
- PnL
- source fetching
- scheduler runtime

Minimum creation rules to design:

- input must be an E2Y-passed candidate set
- candidates must be `WINDOW_15M`
- candidates must be `WINDOW_CLOSED`
- candidates must be `CLEAN_DATA`
- candidates must be `PARTIAL_MEMORY`
- candidates must be E2Q-audited
- candidates must have snapshot links
- no candidate may be dirty or `do_not_train`
- no candidate may be `WINDOW_5M_MICRO_EVENT`
- no 5m row may become main outcome memory
- creation must be idempotent
- creation must produce auditable metadata
- creation must not enable retrieval
- creation must not enable paper decisions
- creation must not enable BUY
- creation must not create positions
- creation must not create PnL

Acceptance gate:

- clean-memory creation rules are documented
- dry-run output says what would be created
- dry-run output creates nothing
- operator approves or revises before implementation

## 10. Revised Lane D - Conservative 15m Clean-Memory Creation, One Boundary Only

Type: code + bounded implementation

Operator approval required: yes

Goal:

Create the first conservative clean-memory row/window artifact only from the already-passed 15m candidate set.

Allowed:

- one explicit operator-approved command
- one bounded creation boundary
- idempotent clean-memory creation
- audit metadata
- tests
- active DB proof
- report output

Not allowed:

- unbounded memory factory
- source fetching
- scheduler runtime
- retrieval activation
- paper decisions
- BUY, SELL, HOLD
- paper positions
- trade events
- paper trade audits
- PnL
- 5m main outcome memory
- paid APIs
- scoring/ranking/confidence/weighted logic
- embeddings/vectors

Acceptance gate:

- exactly expected clean-memory artifact is created
- dirty/audit-only rows remain blocked
- 5m rows remain support-only
- idempotent re-run does not duplicate memory
- report shows zero unexpected table deltas
- retrieval remains off
- paper decisions remain off
- BUY remains off
- positions remain impossible
- PnL remains zero/off
- operator signs off before any next lane

## 11. Revised Lane E - Conservative 15m Memory Factory Readiness Review

Type: report-only review

Operator approval required: yes

Goal:

Only after Lane D proves one safe creation boundary, review whether the system is ready for bounded 15m Memory Factory cycles.

Allowed:

- read-only architecture review
- source budget review
- Source Governor review
- Central Scheduler review
- tracking queue review
- stop-condition checklist
- zero-clean-memory outcome policy
- report-only status

Not allowed:

- source fetching
- scheduler runtime
- new memory creation
- retrieval activation
- paper decisions
- BUY, SELL, HOLD
- positions
- PnL

Acceptance gate:

- readiness checklist exists
- source budgets and stop conditions are explicit
- zero-clean-memory outcome is accepted as valid when evidence fails
- paper decisions remain explicitly off

## 12. Revised Lane F - Bounded Conservative 15m Memory Factory Cycle

Type: code + bounded implementation

Operator approval required: yes

Goal:

Run a bounded conservative 15m Memory Factory cycle only after the one-boundary clean-memory creation path is proven.

Allowed:

- explicit operator-approved command
- operator-approved token list only
- source-governed calls only
- scheduler-controlled path only
- strict token caps
- strict cycle caps
- stop conditions
- clean/dirty memory audit
- dirty rows preserved for audit
- clean rows created only when rules pass

Not allowed:

- unbounded runtime
- broad autonomous discovery loop
- Source Governor bypass
- Central Scheduler bypass
- retrieval activation
- paper decisions
- BUY, SELL, HOLD
- paper positions
- trade events
- audits
- PnL
- live execution
- wallet/private keys
- paid APIs
- scoring/ranking/confidence/weighted logic

Acceptance gate:

- run is bounded
- source budget is respected
- clean memory grows only when evidence passes
- dirty memory remains blocked
- zero clean memories is valid if evidence fails
- no retrieval/paper/BUY/positions/PnL unlock
- operator receives report and signs off before another run

## 13. Revised Lane G - 5m Support Integration Verification

Type: verification or code only if gap exists

Operator approval required: yes

Goal:

Verify that 5m support evidence remains support-only and can inform 15m memory without becoming main outcome memory.

Allowed:

- report-only verification
- fixture tests
- linkage validation
- code only if a specific gap is found

Not allowed:

- 5m main outcome memory
- 5m retrieval unlock
- 5m paper decision unlock
- 5m BUY unlock
- positions
- PnL

Acceptance gate:

- 5m remains support-only
- dirty 5m remains audit-only
- valid 5m support may inform 15m memory only
- no 5m-only unlock path exists

## 14. Revised Lane H - 1h Activation Readiness, No Real Long-Window Runtime Yet

Type: readiness-only

Operator approval required: yes

Goal:

Prepare 1h activation after stable 15m clean-memory behavior exists.

Allowed:

- fixture tests
- schema readiness
- report-only readiness
- no fake long-window data

Not allowed:

- real 1h collection
- fake 1h from 15m
- 4h/12h/24h runtime
- retrieval activation
- paper decisions
- BUY
- positions
- PnL

Acceptance gate:

- 1h readiness exists
- real operation remains 15m-only until separately approved

## 15. Later Lanes

Later lanes may include:

- real 1h activation after 15m clean-memory stability
- 4h readiness
- 12h readiness
- 24h readiness
- controlled clean-memory retrieval expansion after enough clean memories exist
- conservative WAIT/AVOID/NO_ACTION review only after clean memory exists
- BUY unlock documentation review only after much larger clean-memory base
- paper position review only after valid clean-memory-backed paper decisions exist

BUY remains locked until a separate future operator-approved BUY unlock lane.

Positions remain locked until valid clean-memory-backed BUY exists and a separate paper-position lane approves opening simulated positions.

Live trading remains out of V1.

## 16. Stop Conditions Across All Future Work

Stop immediately if any task:

- requires real funds
- requires wallet/private keys/signing
- requires paid APIs
- bypasses Source Governor
- bypasses Central Scheduler
- converts labels into scoring/ranking/confidence/weighted outputs
- uses dirty memory for decisions
- turns 5m into a main outcome memory
- unlocks retrieval before enough clean memories exist
- creates paper decisions before clean-memory-backed gates
- creates BUY before an explicit BUY lane
- creates paper positions before valid clean-memory-backed BUY
- creates PnL before valid position lifecycle exists
- fakes long-window data
- hides source failure
- treats broad context as a direct trade signal
- ignores zero-clean-memory valid outcomes

## 17. Operator Decision

This revised proposal is not active.

The operator must choose one:

### Option A - Adopt This Revised Proposal

Create a documentation-only adoption commit/tag that marks this revised proposal as the active post-E2Y roadmap extension.

### Option B - Revise Again

Edit this document before adoption.

### Option C - Stop

Keep repo anchored at Post-E2Y checkpoint and do not continue implementation.

## 18. Recommended Decision

Recommended decision:

Option A, but only after operator reviews this document.

Recommended next action:

Documentation-only adoption checkpoint.

No implementation should continue until adoption is explicit.

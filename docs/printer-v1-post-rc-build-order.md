
# Printer V1 Post-RC Build Order

This document is the active build-order roadmap for Printer V1 work after the completed V1 Paper Release Candidate.

It supersedes `docs/printer-v1-future-build-order.md` only for work after Phase 38.

It does not delete, rewrite, or invalidate:

* `docs/printer-v1-clean-master-spec.md`
* `docs/printer-v1-final-build-order.md`
* `docs/printer-v1-future-build-order.md`
* `AGENTS.md`

The Future Build Order remains the historical roadmap for Phases 22 through 38.

## Current Post-RC State

Printer V1 has completed:

* Phase 0-20 synthetic checkpoint
* Phase 21 controlled operator CLI
* Phase 22 Future Build Order anchor / operator runbook
* Phase 23 source adapter execution contract
* Phase 24 disabled DexScreener source adapter
* Phase 25 one-shot real source smoke check
* Phase 26 controlled manual intake
* Phase 27 controlled real token snapshots
* Phase 28 controlled context collection
* Phase 29 first real memory window
* Phase 30 memory quality audit
* Phase 31 real memory retrieval
* Phase 32 real-data paper decision activation
* Phase 33 simulated paper position monitor gate
* Phase 34 paper audit and operator review
* Phase 35 scheduler single-tick executor
* Phase 36 bounded multi-tick runtime
* Phase 37 long-run paper validation
* Phase 38 V1 Paper Release Candidate

Known completed anchor:

* Tag: `printer-v1-phase38-v1-paper-release-candidate`

Known post-RC discovery anchor:

* Commit: `7ed76da Add post-RC controlled discovery cycle`
* Tag: `printer-v1-post-rc-controlled-discovery-cycle-1`

Known post-RC checkpoint:

* `data/printer_v1.post-rc-15m-spaced-snapshots-memory-blocked.sqlite3`

## Locked V1 Rules

Printer V1 remains:

* Solana-only
* Solana memecoin-only
* paper-trading only
* no live wallet
* no private keys
* no real funds
* no live execution
* no paid API dependency
* no scoring system
* no ranking system
* no confidence percentage system
* no weighted decision logic
* no engine bypassing Source Governor
* no engine bypassing Central Scheduler
* no paper decision without clean memory comparison
* no paper position without valid clean-memory-backed paper decision
* no memory without completed token evidence windows
* no dirty memory training decisions
* no broad context engine acting as a direct trade signal
* no vectors/embeddings unless explicitly approved later as out-of-scope for V1

Live trading is out of scope for V1.

Wallet/private-key/signing/transaction execution is out of scope for V1.

Real fund movement is out of scope for V1.

## Post-RC Purpose

Post-RC work is not about turning Printer into a live trading bot.

Post-RC work is about:

* growing clean memory
* improving evidence quality
* supporting repeatable evidence windows
* preserving dirty memory for audit
* improving clean-only retrieval
* proving paper realism
* improving operator visibility
* keeping BUY and paper positions locked until the correct gates exist

Printer must not drift into:

* live execution
* wallet logic
* real funds
* paid APIs
* scores
* hype
* autonomous money-bot claims

## Post-RC Discovery Finding

A bounded operator-controlled 15m spaced snapshot cycle was run after RC.

Accepted token:

* token_mint: `pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn`
* pair_address: `4C8KctYZtMTZwV83Y5AcTPVT2aXYYu2t9ZhHdotFGnno`
* chain: `solana`
* token_id: `2`
* pair_id: `2`

Fresh spaced snapshots were collected successfully:

* snapshot_id 7 at about 10:17:51
* snapshot_id 8 at about 10:20:49
* snapshot_id 9 at about 10:23:49
* snapshot_id 10 at about 10:26:49
* snapshot_id 11 at about 10:29:49
* snapshot_id 12 at about 10:32:49

All six snapshots were:

* source_status: COMPLETE
* data_quality_label: CLEAN_DATA
* source_failure_delta: 0

The snapshot cycle worked.

The memory build did not create a new memory window because context and memory were treated as token/pair-level singletons.

Observed blockers:

* `context_already_exists_for_target`
* `memory_window_already_exists_for_target`

This revealed an architectural issue:

A token/pair must be allowed to produce multiple evidence windows over time.

Old dirty memory must remain stored for audit history, but it must not block newer completed evidence.

## Window-Kind Model

Printer must support repeatable evidence windows by `window_kind`.

Supported window identities:

* `WINDOW_5M_MICRO_EVENT`
* `WINDOW_15M`
* `WINDOW_1H`
* `WINDOW_4H`
* `WINDOW_12H`
* `WINDOW_24H`

### 5m Support Window Rule

`WINDOW_5M_MICRO_EVENT` is support-only.

It is not a main outcome memory window.

It must not:

* satisfy the requirement for a completed 15m/1h/4h/12h/24h memory outcome window
* unlock retrieval by itself
* unlock paper decisions
* unlock BUY
* open paper positions
* create PnL

It may create or refresh support evidence/micro-event labels such as:

* fast pump
* fast dump
* wick-only move
* late-buy trap
* tradable micro-pump
* untradable micro-pump
* micro-exit realism
* held-to-15m result

Main memory windows may reference valid 5m support evidence as context.

Dirty or DO_NOT_TRAIN 5m support evidence remains audit-only.

Older dirty 5m evidence must not block newer 5m support evidence.

Older dirty 5m evidence must not pollute newer main memory windows.

### Main Outcome Memory Windows

Main memory windows are:

* `WINDOW_15M`
* `WINDOW_1H`
* `WINDOW_4H`
* `WINDOW_12H`
* `WINDOW_24H`

The same token/pair can have multiple windows of the same `window_kind` over time.

The same token/pair can have different `window_kind` records over time.

Memory windows must be tied to a specific evidence identity, not only token_id + pair_id + window_kind.

Acceptable evidence identity fields include:

* snapshot_start_id
* snapshot_end_id
* window_start_at
* window_end_at
* source_reference
* cycle_id

Use the least invasive durable design that preserves auditability.

## Post-RC Lane 1 — Source-of-Truth Post-RC Anchor

Goal:

Create this Post-RC Build Order and update AGENTS.md so Codex knows that all work after Phase 38 must follow this document.

Allowed:

* documentation only
* AGENTS.md update
* roadmap clarification

Not allowed:

* source code changes
* migration changes
* test changes
* source adapters
* live fetching
* scheduler execution
* memory generation
* paper decisions
* paper positions
* runtime

Exit gate:

* `docs/printer-v1-post-rc-build-order.md` exists
* `AGENTS.md` points Codex to this doc for work after Phase 38
* old Future Build Order remains preserved as Phase 22-38 history
* V1 rules remain unchanged

## Post-RC Lane 2 — Repeatable Evidence Window Architecture

Goal:

Fix context/memory singleton behavior so the same token/pair can produce multiple evidence windows over time.

Must support architecture for:

* `WINDOW_5M_MICRO_EVENT`
* `WINDOW_15M`
* `WINDOW_1H`
* `WINDOW_4H`
* `WINDOW_12H`
* `WINDOW_24H`

Rules:

* 5m remains support-only
* main outcome windows remain 15m, 1h, 4h, 12h, 24h
* same token/pair can have multiple windows over time
* old dirty memory remains stored for audit
* old dirty memory must not block newer completed evidence
* audit/retrieval must target a specific memory_window_id/evidence window
* dirty/DO_NOT_TRAIN memory remains blocked

Allowed:

* minimal schema changes if required
* context/memory/audit/retrieval targeting fixes
* tests
* fixture tests for all window kinds
* persistent DB proof only for current WINDOW_15M case

Not allowed:

* BUY unlock
* paper positions
* PnL
* live trading
* wallets/private keys
* scoring/ranking/confidence systems
* unbounded runtime

Exit gate:

* fresh snapshots 7-12 can create or target a new 15m memory window
* snapshot coverage is correctly recognized
* if context remains unknown, dirty reason is context-related, not false missing snapshots
* retrieval stays clean-only
* paper decisions and positions remain blocked

## Post-RC Lane 3 — Clean Context Freshness / Window Context Targeting

Goal:

Ensure context rows can be refreshed or safely targeted per evidence window without fabricating context.

Allowed:

* context freshness rules
* context targeting by snapshot/window/cycle
* stale/unknown context labels
* tests

Not allowed:

* inventing context
* forcing clean memory
* turning broad context into a trade signal

Exit gate:

* new windows are not blocked forever by old `context_already_exists_for_target`
* unknown context remains visible and blocking

## Post-RC Lane 4 — Repeatable 15m Memory Growth Cycles

Goal:

Run repeated controlled 15m cycles across approved TRACK_FAST/TRACK_NORMAL tokens to grow audited memory.

Allowed:

* bounded operator-controlled runs
* one to three candidates per cycle
* manual/operator-approved cycles
* clean/dirty memory audit
* clean-only retrieval checks

Not allowed:

* autonomous unbounded operation
* paper BUY unlock
* positions
* PnL
* live trading

Exit gate:

* multiple 15m windows can be created over time
* clean memory count grows only when rules genuinely pass
* dirty memory remains blocked

## Post-RC Lane 5 — 5m Micro-Event Support Evidence Hardening

Goal:

Make 5m micro-event evidence repeatable and linkable into main windows without becoming a main outcome window.

Allowed:

* `WINDOW_5M_MICRO_EVENT` support evidence
* micro-event labels
* linkage to 15m context
* tests

Not allowed:

* 5m as main outcome memory
* 5m unlocking retrieval/paper decisions/BUY/positions/PnL by itself

Exit gate:

* 5m support evidence can repeat over time
* dirty 5m evidence stays audit-only
* valid 5m support can inform 15m memory without replacing it

## Post-RC Lane 6 — Longer Window Activation Readiness

Goal:

Prepare 1h/4h/12h/24h memory-window architecture, but do not run real long windows until 15m is proven.

Allowed:

* fixture tests
* schema readiness
* generic window_kind code paths

Not allowed:

* real 1h/4h/12h/24h collection
* fake long-window data from 15m snapshots
* runtime expansion

Exit gate:

* longer windows are structurally supported
* real operation remains 15m-only until approved

## Post-RC Lane 7 — Controlled Clean-Memory Retrieval Expansion

Goal:

After enough clean memories exist, improve retrieval reporting without adding scores.

Allowed:

* clean-only retrieval filters
* best/worst historical action summaries
* conflicting memory reporting
* no-score similarity labels

Not allowed:

* numeric scores
* confidence percentages
* embeddings/vector search unless separately approved
* dirty memory retrieval

Exit gate:

* retrieval can explain similar clean memories without using dirty data

## Post-RC Lane 8 — Paper Decision Unlock Review, WAIT/AVOID First

Goal:

Only after clean memory exists, review whether paper decisions should resume with conservative WAIT/AVOID/NO_ACTION first.

Allowed:

* paper decision audit review
* WAIT/AVOID/NO_ACTION validation
* operator approval gates

Not allowed:

* BUY unlock unless explicitly approved in a later lane
* positions unless a valid clean-memory-backed paper decision exists

Exit gate:

* no BUY until separate operator-approved BUY unlock lane

## Post-RC Lane 9 — BUY Unlock Preconditions, Documentation Only

Goal:

Define the exact future conditions required before BUY can ever be allowed in paper mode.

Allowed:

* documentation
* checklist
* risk gates
* clean memory minimums
* exit realism requirements

Not allowed:

* code unlock
* BUY action
* positions
* PnL

Exit gate:

* operator has a strict BUY unlock policy, but BUY remains disabled

## Post-RC Lane 10 — Later Paper Position Re-Activation Review

Goal:

Only after valid clean-memory-backed decisions exist, review simulated paper position opening again.

Allowed:

* review only
* tests
* operator gate

Not allowed:

* live trading
* wallet/private keys
* real funds

Exit gate:

* paper positions remain impossible without valid clean-memory-backed paper decision

## Post-RC Required Report Format

Every post-RC task must end with:

* Files changed
* What was built
* What was not touched
* Tests/checks run
* Pass/fail status
* Risks or concerns
* Next recommended lane

## Post-RC Locked Rule

Post-RC Printer work exists to grow clean audited memory and prove realistic paper behavior.

It must not become live trading.

It must not loosen V1 restrictions.

It must not make dirty memory useful for decisions.

It must not create BUY or paper positions before clean-memory-backed gates justify them.

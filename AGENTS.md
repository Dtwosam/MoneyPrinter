# Printer V1 Build Rules

## Active Authority Stack and Current-Lane Rule — 2026-08-27

This section is the current authority anchor for Printer V1 / Moneygoals work.
It supersedes any older `source of truth`, `current active lane`, `current
authority`, or `next correct action` wording later in this file when that wording
conflicts with this section. Historical text remains preserved as evidence.

Use this active source stack, in order:

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`

`docs/printer-v1-memory-growth-build-order-v2.md` is the active memory-growth
build order inside this stack. It is not the sole source of truth.

Use `CURRENT_HANDOFF.md` only for current lane, current commit, latest completed
work, blockers, and next permitted action. If `CURRENT_HANDOFF.md` conflicts
with the authority stack above, the authority stack wins.

Historical roadmaps, old lane documents, old chats, previous handoffs, and
older current-looking pointers in this file are historical evidence only unless
explicitly re-adopted.

For every suggested change, shortcut, next step, repair, workflow, proof, or new
lane:

- check it against the active source stack, active build order, and
  `CURRENT_HANDOFF.md`;
- reject or correct anything that skips required sequencing, weakens a
  safety/evidence rule, or drifts from V1;
- distinguish proven code defects from source scarcity, provider limitations,
  honest market blocks, missing evidence, documentation assumptions, and
  infrastructure requirements before proposing implementation.

Every major capability must preserve:

`audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout`

Use minimum sufficient risk-based verification. Do not request broad regression
suites unless the change risk or lane closeout requires them.

### Current V2-9.8B consumed Sep-1 Standard-4H scope-propagation repair — 2026-09-01

Consumed authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260901T181024Z_ab6c68fe`

Final state:

`CONSUMED / CHILD_EXITED_NONZERO / PERMANENTLY NON-REUSABLE`

Authorized HEAD for that one-shot:

`eefd909fe40b14a6459154c71ba56ace8be08b4f`

Execution:

`20260901T191450Z-520d6a348621`

Terminal cause:

`ValueError:CAMPAIGN_SOURCE_REQUEST_SCOPE_REQUIRED`

Classification:

`COMMITTED_CODE_DEFECT` / `CAMPAIGN_SOURCE_REQUEST_SCOPE_PROPAGATION_LOSS`

Governing closeout:

`docs/printer-v1-v2-9-8b-campaign-source-request-scope-propagation-repair-closeout.md`

This block supersedes older current-looking Standard-4H next-lane pointers later
in this file for current-lane selection only. Historical consumed/stale
authorization text remains evidence. The consumed Sep-1 authorization must remain
in every future Standard-4H prior non-reuse trust root. Do not retry, rerun,
resume, restart, or create a successor from that run.

The exact current permitted lane is:

```text
POST-REPAIR FRESH EXACT-HEAD / EXACT-DB READINESS / GOVERNANCE ONLY
```

Use `CURRENT_HANDOFF.md` for the live HEAD after this closeout commit, latest
completed work, and next permitted action.

This does **not** authorize `apply_authorization_once`, application-marker
creation, Printer execution, child launch, another campaign, provider/RPC/
WebSocket calls, Central Scheduler runtime, authoritative DB mutation,
retry/rerun/resume/restart/successor, retrieval, BUY/SELL/HOLD, positions,
trades, audits, PnL, or `WINDOW_12H` / `WINDOW_24H`.

### Current V2-9.8B stale Standard-4H authorization exact-HEAD-drift closeout — 2026-08-31

Final pre-application approval verdict:

`V2_9_8B_FROZEN_STD4H_PREAPPLICATION_APPROVAL_BLOCKED`

Blocker:

`AUTHORIZATION_EXACT_HEAD_BINDING_DRIFT`

Stale frozen authorization ID:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`

Frozen authorization SHA-256 (byte-identical; do not alter):

`5cd5ca47761458023061e4627999df13fb1ac9b80c80bc836b7e4ba012de290f`

Stale authorization final state:

`STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION`

Current repository HEAD before this closeout:

`2913c03f4e8cf8246b8ca759721799a92cddf39c`

Frozen repository HEAD binding (stale):

`abdd210d2d1e0788d241d8a26f09b9a60a105912`

Exact authoritative DB SHA-256:

`859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`

Governing stale closeout:

`docs/printer-v1-v2-9-8b-stale-standard-4h-authorization-head-drift-closeout.md`

Prior package-review closeout remains historically correct as written:

`docs/printer-v1-v2-9-8b-next-standard-4h-authorization-package-review-closeout.md`

Governing design (do not redo):

`docs/printer-v1-v2-9-8b-next-standard-4h-authorization-preparation-boundary-design.md`

Binding classification:

- governance / state-binding blocker;
- NOT a committed-code defect;
- DB binding passed;
- DB health passed;
- temporal validity passed at audit time;
- runtime / ownership zero-state passed;
- authorization SHA / integrity passed;
- Standard-4H / governance envelope passed;
- authorization remained unconsumed and unapplied.

The package-review closeout documentation commit changed repository HEAD after
package preparation. Therefore the frozen authorization can never satisfy the
exact-HEAD application contract against the current repository.

Do not alter, rebind, renew, delete, rename, move, apply, or automatically
replace the stale package. No application or consumption occurred. Do not
describe it as consumed. From this closeout forward,
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46` is an
active-governance-required prior non-reusable authorization ID for every future
Standard-4H package; future complete `prior_authorizations_non_reusable` trust
roots must include it in addition to every already-required prior ID, including
consumed Aug-30 `...a89ed6bc` and Aug-28 `...5fcb1bf5`.

Existing canonical owners remain authoritative:

- document validator:
  `validate_four_token_standard_four_hour_authorization_document`
- application/consumption owner: `apply_authorization_once`
- operational policy: `exact_operational_policy()`
- profile: `FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE`
- zero-state: `assert_four_token_standard_four_hour_zero_state`
- prior non-reuse: `validate_prior_authorizations_non_reusable`

```text
Raw historical slot state alone must not establish active execution authority.
Canonical campaign/run/supervision/lease/Scheduler/factory/progression/pre-admission ownership truth governs active-work readiness.
```

Do not mutate the historical Aug-30 Cycle-2 `SELECTED` rows.

Standard-4H envelope remains exactly: Solana-only; Solana memecoin-only;
paper-only; two cycles; exactly 2 concurrent active token slots; up to 4
distinct identities campaign-wide; Cycle 2 fresh/disjoint; `WINDOW_15M` →
hard-gated `WINDOW_1H` → hard-gated `WINDOW_4H` → stop; `WINDOW_5M`
support-only; `WINDOW_12H` / `WINDOW_24H` locked; no automatic
retry/rerun/resume/restart/successor.

This stale-authorization closeout and fresh-preparation re-entry become active
only when this six-doc package is committed. Until that commit exists, do not
prepare another authorization. Do not invent the future closeout commit SHA.
The later preparation must bind the actual HEAD produced by that commit.

After this package is committed, the exact current permitted lane is:

```text
FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — STALE PRIOR AUTHORIZATION SEALED NON-REUSABLE
```

Exact currently permitted action:

```text
Prepare exactly one fresh exact-HEAD / exact-DB one-shot Standard-4H authorization package using the existing canonical authorization owners, including V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46 in the complete prior non-reuse trust root, and stop unconsumed for independent package review.
```

That lane is separately approved fresh preparation only. It is NOT an automatic
successor or retry. Do not redo the completed authorization-boundary design. Do
not reopen the Aug-30 repair. Do not require another broad readiness audit
solely because this package became stale.

It does **not** itself authorize `apply_authorization_once`,
application-marker creation, Printer execution, child launch, another campaign,
provider/RPC/WebSocket calls, Central Scheduler runtime, authoritative DB
mutation, retry/rerun/resume/restart/successor, retrieval, BUY/SELL/HOLD,
positions/trades/audits/PnL, or `WINDOW_12H` / `WINDOW_24H`.

Preserve the builder sequence:

```text
readiness -> design/specification -> preparation -> independent package review -> explicit application/execution approval -> one-shot bounded execution/proof -> closeout
```

Do not collapse review, application approval, and execution into one action.

Any future approved remote-host implementation must preserve the existing
one-shot wrapper as the operational application boundary, `Restart=no`, no
timer/watchdog/reboot relaunch, cooperative safe-stop through existing campaign
supervision, exact remote HEAD+DB authorization binding after final remote
identity exists, one sole authoritative operational DB writer/host, no Mac/VPS
write overlap, Source Governor and Central Scheduler authority, and consumed
authorization permanent non-reuse.

Permanent V1 locks remain unchanged: Solana-only; Solana memecoin-only;
paper-trading only; no live wallet/private keys/signing/real funds/live
execution; no paid API dependency; no scoring/ranking/confidence percentages or
weighted decision logic; no embeddings/vectors unless explicitly approved; no
Source Governor or Central Scheduler bypass; no dirty memory for retrieval or
decisions; no retrieval or financial capability before its explicit approved
lane. `WINDOW_5M_MICRO_EVENT` remains support-only. `WINDOW_12H` and
`WINDOW_24H` remain locked. No automatic retry/rerun/resume/restart.

Printer V1 is a Solana-only memecoin memory and paper-trading machine.

Printer V1 is paper-trading only.

Use these documents as the source of truth:

- docs/printer-v1-clean-master-spec.md

- docs/printer-v1-final-build-order.md

- docs/printer-v1-memory-factory-guide.md

- docs/printer-v1-buy-unlock-preconditions.md

- docs/printer-v1-paper-position-reactivation-review.md

- docs/printer-v1-post-lane10-proposed-next-build-order.md

## Core Goal

Printer's goal is to become a realistic paper-trading money machine by collecting clean Solana memecoin data, building clean historical memory, comparing current setups against past clean memory, making paper-only decisions, and auditing whether those decisions protected capital or produced realistic paper profit.

Printer must avoid fake profit, dirty memory, forced trades, and rushed implementation.

## Locked V1 Rules

Do not add:

- live trading

- wallet connection

- private keys

- real fund movement

- paid API dependencies

- scoring systems

- buy score

- confidence score

- safety score

- liquidity score

- chart score

- flow score

- market score

- combined score

Printer decisions can only be:

- BUY

- SELL

- HOLD

- WAIT

- AVOID

- NO_ACTION

All decisions must come from clean historical memory comparison.

If there is not enough clean memory, Printer must choose WAIT, AVOID, or NO_ACTION depending on risk.

## Post-RC Build Order Anchor

The Future Build Order has been completed through Phase 38 / V1 Paper Release Candidate.

For all work after Phase 38, Codex must read and follow:

`docs/printer-v1-post-rc-build-order.md`

This Post-RC Build Order supersedes `docs/printer-v1-future-build-order.md` only for work after Phase 38.

The Future Build Order remains preserved as the historical roadmap for Phases 22 through 38.

The Final Build Order remains preserved as the historical roadmap for the original Phase 0 through Phase 21 sequence.

Post-RC work must not loosen any V1 restriction.

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
* no dirty memory training decisions
* no broad context engine acting as a direct trade signal

Post-RC work must proceed lane by lane.

Do not skip lanes.

Do not convert post-RC memory growth into live trading.

Do not unlock BUY without an explicit future operator-approved BUY unlock lane.

Do not open paper positions without a valid clean-memory-backed paper decision.

Post-RC Lane 9 BUY unlock preconditions are documentation-only policy:

`docs/printer-v1-buy-unlock-preconditions.md`

This policy defines future BUY review preconditions only. It does not unlock BUY, authorize BUY/SELL/HOLD decisions, allow paper positions, create PnL, or loosen any V1 restriction.

Post-RC Lane 10 paper position re-activation review is documentation-only policy:

`docs/printer-v1-paper-position-reactivation-review.md`

This policy defines future paper-position review preconditions only. It does not reactivate paper positions, authorize BUY/SELL/HOLD decisions, create trade events, create paper trade audits, create PnL, or loosen any V1 restriction.

## Post-Lane 10 Active Roadmap Extension

After completed Post-RC Lane 10 and the post-Lane-10 architecture planning checkpoint, the active roadmap extension is:

`docs/printer-v1-post-lane10-proposed-next-build-order.md`

The original Post-RC Build Order remains preserved as the completed Lane 1-10 source. The post-Lane-10 next build order is active only as the roadmap extension after Lane 10 and architecture planning were completed.

This adoption does not unlock BUY, SELL/HOLD, paper positions, trade events, paper trade audits, PnL, live trading, wallets, private keys, paid APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or vectors.

The next active lane is Proposed Lane A / Architecture and Document Adoption Checkpoint unless the operator explicitly chooses a different approved lane.

The 5m window remains support-only.

The first Memory Factory implementation must keep paper decisions off.

## Future Build Order Anchor

Before any phase after Phase 21, Codex must read:

`docs/printer-v1-future-build-order.md`

Codex must follow that future build order unless the operator explicitly replaces it.

Rules:

* Do not skip phases.

* Do not convert future phases into live trading.

* Do not build runtime before the runtime phase.

* Do not build scheduler execution before the scheduler execution phase.

* Do not build source adapters before the source adapter phase.

* Do not fetch real data before the real source smoke-check phase.

* Do not create token/pair rows from real data before the controlled intake phase.

* Do not create real token snapshots before the snapshot phase.

* Do not create real memory before the real memory phase.

* Do not create real-data paper decisions before the paper decision phase.

* Do not open simulated paper positions before the simulated paper position phase.

* Do not introduce wallet/private-key/signing/transaction/live-trading logic.

* Do not introduce scoring/ranking/confidence systems.

* Do not introduce vectors/embeddings unless explicitly approved as out-of-scope for V1.

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

* no engine bypassing Source Governor

* no engine bypassing Central Scheduler

* no paper decision without clean memory comparison

* no paper position without valid clean-memory-backed paper decision

Codex must stop after the requested phase and provide a pass/fail report.

## Architecture Rules

Printer must work as one machine.

No engine may bypass the central scheduler or source governor.

No engine may create its own independent API loop.

No engine may compete with token-level snapshots.

No engine may write isolated memory outside the shared memory pipeline.

No engine may duplicate source-fetching logic that belongs inside the source governor.

Token-level snapshots and open paper-trade monitoring always take priority over broad context engines.

## Resource Priority Order

When resources, rate limits, or scheduling capacity are tight, use this priority order:

1\. Open paper-trade monitoring

2\. Exit-risk token snapshots

3\. TRACK_FAST / micro-event token snapshots

4\. TRACK_NORMAL token snapshots

5\. Memory-window close snapshots

6\. Safety and liquidity refreshes

7\. Discovery refresh

8\. Market regime context

9\. Solana chain heat context

10\. Backup checks

## Build Order

Follow the final build order:

1\. Project Law + AGENTS.md

2\. Database Foundation

3\. Source Registry + Source Governor

4\. Central Scheduler + Resource Governor

5\. Token Lifecycle + Tracking Queue

6\. Discovery Engine

7\. Token-Level Snapshot System

8\. Market Regime Engine

9\. Solana Chain Heat Engine

10\. Safety / Rug Filter Engine

11\. Liquidity + Exit Engine

12\. Trading Flow Engine

13\. Chart / Volatility Engine

14\. Micro-Event Engine

15\. Episode / Memory Engine

16\. Memory Retrieval + Similarity Engine

17\. Paper Decision Engine

18\. Paper Trade Monitor

19\. Paper Audit Engine

20\. Reporting + Operator Review

21\. Hardening + Long-Run Paper Validation

Build only the requested phase.

Do not build future phases early.

## Source Rules

Printer V1 may only use free/public data sources.

Allowed free-first sources:

- Direct Pump.fun on-chain activity through approved free/public Solana RPC
  remains available to the deferred candidate-acquisition subsystem; it is not
  an active operational prerequisite

- Direct Pump.fun migration and PumpSwap state through approved free/public
  Solana RPC remains available to the deferred candidate-acquisition subsystem;
  it is not an active operational prerequisite

- DexScreener

- GeckoTerminal

- PumpPortal free/keyless launch and migration locator through the proven
  Source-Governed operational intake only; no metered trade/account stream,
  wallet, funding, paid fallback, or independent pair authority

- Alternative.me Fear \& Greed

- CoinGecko free/public/Demo

- DefiLlama

- GoPlus where available

- Solana public RPC

- Helius free tier

- Jupiter quote API for paper simulation only

Do not add dependency on:

- paid Birdeye

- paid LunarCrush

- paid X API

- paid smart-wallet tools

- paid social sentiment tools

- paid execution infrastructure

If a feature requires paid data, do not build it in Printer V1.

## Memory Rules

Printer only learns from completed memory windows.

Main memory windows:

- 15 minutes

- 1 hour

- 4 hours

- 12 hours

- 24 hours

Support micro-event window:

- 5 minutes

The 5-minute window is not a main outcome window. It only explains fast pump/dump behavior inside or before the larger windows.

Dirty, stale, incomplete, delayed, or broken data must not become clean memory.

Use memory quality labels:

- CLEAN_MEMORY

- PARTIAL_MEMORY

- DIRTY_MEMORY

- DO_NOT_TRAIN

DIRTY_MEMORY and DO_NOT_TRAIN must never be used for decisions.

## Decision Rules

Every Printer decision must follow this template:

Decision:

Current setup:

Market condition:

Solana condition:

Similar clean memories found:

What happened in those memories:

Best historical action:

Worst historical action:

Current action:

Reason:

Invalidation condition:

Paper trade status:

Printer must not make a BUY, SELL, or HOLD decision from one signal alone.

Market regime is context only.

Solana chain heat is context only.

Discovery is intake only.

Safety is protection only.

Liquidity and exit realism determine whether paper profit was realistic.

Trading flow and chart behavior are memory labels, not standalone signals.

## Paper Trading Rules

Printer V1 is paper trading only.

Paper trades must record:

- entry time

- entry price

- entry liquidity

- entry source status

- matched clean memories

- decision reason

- invalidation condition

- exit condition

- exit time

- exit price

- exit liquidity

- realistic or unrealistic profit result

A paper profit is not clean unless entry and exit were realistic.

If the chart moved but Printer could not realistically enter or exit, the result must be marked as unrealistic or fragile.

## Build Discipline

Do not make unrelated refactors.

Do not rename core concepts unless explicitly asked.

Do not edit files outside the requested scope unless required, and explain why.

Do not run destructive commands.

Do not add live trading placeholders.

Do not add wallet placeholders.

Do not add paid API placeholders.

Do not loosen rules to make tests pass.

Prefer small, complete build lanes over broad patches.

Each phase must have a clear pass/fail result before moving to the next phase.

## Production-Path Completeness Gate

Before implementing any non-trivial runtime behavior or repair:

1. Trace the affected production path and confirm the requested behavior maps
   to a real reachable production state.

2. Any new runtime state, exception, status, flag, envelope, or classification
   must have a real production producer and consumer. Test-only injection is
   not a substitute for a production producer.

3. Tests must inject the underlying condition being classified, not directly
   inject the expected classification/result.

4. For a new failure/classification boundary, prove the intended case and the
   fail-closed/opposite case at the same production boundary when practical.

5. If the requested design assumes a production state that does not actually
   exist, STOP before implementation and report the design/source/provider/
   evidence gap instead of inventing behavior.

Passing tests alone do not prove implementation completeness.
Use minimum sufficient source inspection and risk-based verification.

This gate applies only to non-trivial runtime or semantic work. It does not
require heavyweight preflight for formatting, dead imports, straightforward
renames, documentation-only changes, or other clearly non-semantic edits.
The existing Risk-Based Verification Policy remains authoritative.

## Risk-Based Verification Policy

Use minimum sufficient verification based on change risk.

- Documentation, audit, and design work: static checks only.

- Narrow code changes: changed tests, nearest affected contract tests, compilation, and diff checks.

- Cross-cutting changes involving migrations, Source Governor, Central Scheduler, cadence, continuity, supervision, DB isolation, budgets, or memory quality: focused tests plus directly affected regressions.

- Run broad/full suites only at major lane closeout, before a live proof, before a release/checkpoint, or after a broad architectural change.

- Do not expand test scope merely because unrelated pre-existing failures appear. Confirm them against the baseline, document them, and defer them unless they affect the current lane.

- Never weaken tests, safety gates, evidence rules, or required bounded proof to save time or credits.

## Required Response Format

Every Codex task must end with:

- Files changed

- What was built

- What was not touched

- Tests/checks run

- Pass/fail status

- Risks or concerns

- Next recommended phase

## Current Active Build Order Anchor

For all Printer V1 / Moneygoals work after the Post-Lane10 adoption checkpoint, the active build order is:

`docs/printer-v1-post-lane10-proposed-next-build-order.md`

This file must be used actively alongside the higher-authority source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-post-lane10-architecture-review.md`
- `docs/printer-v1-post-lane10-proposed-next-build-order.md`

Confirmed completed/anchored from the Post-Lane10 reconciliation:

- Post-Lane10 architecture planning: done
- Post-Lane10 next build order adoption: done
- Lane A adoption checkpoint: done
- Lane B conservative 15m Memory Factory readiness review: done
- Lane C source budget/governor verification: done
- Lane D scheduler/tracking/window-close readiness: done
- Lane E conservative 15m Memory Factory implementation: advanced but still partial
- Lane F 5m support evidence integration: mostly done/hardened through E2V/E2W/E2W-C
- E2X and E2Y: extra read-only safety hardening, not replacement roadmap lanes
- Post-E2Y drift checkpoint: documentation-only note
- Post-E2Y revised next build order proposal: documentation-only proposal, NOT ACTIVE

Do not restart from Lane B, Lane C, or Lane D.

Do not treat `docs/printer-v1-post-e2y-revised-next-build-order.md` as active unless the operator explicitly asks for a future adoption.

Do not invent new implementation lanes blindly.

The next correct action after the current anchor is a read-only Lane E/F closeout map to confirm what remains in the active Post-Lane10 build order.

Most likely remaining gap:

- clean-memory creation/write-target boundary is not complete yet

The following remain locked unless a later explicit active build-order lane unlocks them:

- clean-memory creation
- retrieval activation
- paper decisions
- BUY, SELL, HOLD
- paper positions
- trade events
- paper audits
- PnL
- live execution
- wallet/private-key/signing logic
- source fetching outside governed approved commands
- scheduler runtime expansion
- paid APIs
- scoring/ranking/confidence/weighted logic
- embeddings/vectors

<!-- PRINTER_V1_MEMORY_GROWTH_BUILD_ORDER_ANCHOR_START -->

## Memory Growth Build Order Anchor

After V2-0 current-state audit, V2-1 adoption/reset, and the V2-9 final closeout, Codex must use the following memory-growth source stack for Printer V1 / Moneygoals memory-growth work.

Active memory-growth source of truth:

- docs/printer-v1-memory-growth-build-order-v2.md

Required supporting audit/readiness/source-stack documents:

- docs/printer-v1-memory-growth-automation-audit.md
- docs/printer-v1-current-state-memory-growth-audit.md
- docs/printer-v1-v2-9-final-closeout.md
- docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration.md
- docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration-closeout.md
- docs/printer-v1-v2-9-8b-four-token-standard-4h-source-stack-adoption.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-capacity-feasibility-audit.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-roadmap-adoption.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-combined-audit.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-complete-design.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-implementation-closeout.md
- docs/printer-v1-v2-9-8b-pump-migration-observation-decoupling-audit.md
- docs/printer-v1-v2-9-8b-pump-migration-observation-decoupling-design.md
- docs/printer-v1-v2-9-8b-pump-migration-observation-decoupling-implementation-closeout.md
- docs/printer-v1-v2-9-8b-bounded-live-n2-pump-migration-decoupling-proof-closeout.md

Historical previous active roadmap:

- docs/printer-v1-memory-growth-build-order.md

Historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Current active memory-growth lane after V2-9.8A operator activation PASS:

- V2-9.8B — Active Bounded Memory Growth Operations

Current adopted bounded operational envelope (2026-08-26 source-stack sync):

- docs/printer-v1-v2-9-8b-four-token-standard-4h-source-stack-adoption.md
- policy family: `V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1`
- two cycles; exactly two concurrently active token slots; up to four distinct
  token identities across the full two-cycle campaign
- "four-token" does not mean concurrent capacity four; concurrent capacity
  remains exactly 2; no increase to 3 or 4 concurrent tokens is authorized
- standard lifecycle: `WINDOW_15M` → hard-gated `WINDOW_1H` → hard-gated
  `WINDOW_4H` → stop; `WINDOW_12H` / `WINDOW_24H` remain locked
- Cycle-2 fresh slots must be campaign-history disjoint from earlier admitted
  cycles
- candidate-acquisition foundation / N2 / N7 / global Pump cursor/recovery
  remain preserved but deferred and are not an operational prerequisite
- this adoption establishes the capability envelope only; it creates no
  authorization and unlocks no campaign

### Operational Factory Active-Path Restoration (2026-07-29)

The active-path restoration design is:

- `docs/printer-v1-v2-9-8b-operational-factory-active-path-restoration.md`

The selected last-good operational implementation checkpoint is
`7c38f13816169c69697ed19893b7e12802d9b1b7`. The first commit that placed the
candidate-acquisition overhaul in the active operational critical path is
`219ad8125a75f52686bfbf5953be0fa4cdca4712`.

The restored active path is the proven two-token operational
discovery/selection/tracking route with later independent supervision,
provenance, reporting, replay, database-mode, holder/evidence-quality and lock
protections preserved. It supports the current migration ledger through 049.

Candidate-acquisition foundation, N2/N7, global Pump cursors, cursor recovery
and migration-observation admission are now deferred/experimental. Their code,
migrations, tables and historical evidence remain intact but are not an
operational prerequisite or authority for the active factory. The active
operational command must not read, reset, advance or interpret their cursors or
recovery rows.

Historical restoration checkpoint — preserved for provenance, not current
next-lane authority: on restoration PASS, the exact next permitted task was
operator review of the restoration branch and closeout only. PASS did not
authorize the published operational command, a campaign, N2, N7, recovery,
cursor reset, provider/RPC work, retrieval or any financial capability. The
later 2026-08-26 four-token standard-4h source-stack adoption and its
post-synchronization readiness pointer are themselves historical for next-lane
purposes. Current next-lane authority is the Cycle-1 historical-disjointness
repair closeout / `CURRENT_HANDOFF.md` post-repair fresh next-bounded-campaign
authorization readiness/governance lane.

The candidate-acquisition history below is preserved as a historical/deferred
record. It does not override this restoration anchor.

Historically inside V2-9.8B, the candidate-acquisition foundation roadmap adoption and the
combined foundation implementation are closed PASS. The Direct Pump/PumpSwap
contract audit, post-foundation integration, canonical live transport-owner
repair, and comprehensive pipeline repair are complete. The final post-repair
bounded live candidate-acquisition proof is closed
`V2_9_8B_FINAL_POST_REPAIR_BOUNDED_LIVE_CANDIDATE_ACQUISITION_PROOF_BLOCKED`
(closeout:
`docs/printer-v1-v2-9-8b-final-post-repair-bounded-live-candidate-acquisition-proof-closeout.md`).
The foundation mint-identity admission repair is closed PASS. The separately
authorized post-mint-repair `ACQUISITION_ONLY_N2` proof is closed
`V2_9_8B_POST_MINT_ADMISSION_REPAIR_LIVE_N2_PROOF_BLOCKED` on
`CURSOR_START_MISMATCH`. The separate durable cursor-to-live-range continuity
audit and repair is closed `V2_9_8B_DURABLE_CURSOR_LIVE_RANGE_REPAIR_PASS`. The
subsequent post-cursor-repair live N2 proof is closed
`V2_9_8B_POST_CURSOR_REPAIR_LIVE_N2_PROOF_BLOCKED` (closeout:
`docs/printer-v1-v2-9-8b-post-cursor-repair-live-n2-proof-closeout.md`). It ran
exactly once, passed explicit `FORWARD` bootstrap while preserving historical
`BACKWARD` heads, and blocked at foundation on `IDENTITY_MERGE_FAILURE` /
`IDENTITY_NOT_MERGED` because exact quote identity was absent for all four
cohort candidates. N7 is `NOT_RUN`. The subsequent Pump migration observation
decoupling audit/design and implementation/offline-proof lane is closed
`V2_9_8B_PUMP_MIGRATION_OBSERVATION_DECOUPLING_IMPLEMENTATION_PASS`. Global
Pump migration observation is optional coverage; exact Pump graduation now
requires candidate-specific finalized migration plus exact PumpSwap Pool
verification. The separately authorized bounded live N2 decoupling proof is
closed `V2_9_8B_BOUNDED_LIVE_N2_PUMP_MIGRATION_DECOUPLING_PROOF_BLOCKED` on
`OPERATION_ACCOUNTING_MISMATCH` in optional-global
`pumpfun_migration_transaction` work. The optional-global operation-accounting
repair and offline proof is closed
`V2_9_8B_OPTIONAL_GLOBAL_OPERATION_ACCOUNTING_REPAIR_PASS`. The separately
authorized repaired-boundary live N2 proof is closed
`V2_9_8B_BOUNDED_LIVE_N2_OPTIONAL_GLOBAL_ACCOUNTING_REPAIR_PROOF_BLOCKED`
on honest `OBSERVATION_ROW_CEILING` budget exhaustion after the optional-global
operation accounting reconciled exactly. The historical next task at that
checkpoint was operator review of that terminal closeout and redacted evidence;
the restoration anchor above now supersedes it. No automatic run, retry,
recovery, campaign, cursor reset, N7, or later runtime lane is authorized.

The deferred candidate-acquisition subsystem's historical authority model is:

1. direct Pump.fun on-chain activity for exact launch origin;
2. direct Pump.fun migration plus PumpSwap evidence for exact graduation and
   canonical pool identity;
3. DexScreener and GeckoTerminal for direct candidate nomination and their
   supported current market, liquidity, activity, age, and coverage facts;
4. approved Solana RPC providers for exact on-chain verification; and
5. PumpPortal only as an optional governed locator after its authentication,
   wallet, free-versus-metered, and cost contract is resolved.

Aggregator observations never replace exact Pump origin or exact joined
Pump-migration/PumpSwap graduation evidence. The integrated acquisition owner has
bounded live observation and restart-safe cursor-based historical backfill for
missed Pump creation and migration events under one Source-Governed,
Scheduler-led owner. Unknown or unsupported Pump/PumpSwap instruction, event,
account, layout, quote-mint, extension, or PDA contracts fail closed. Refresh
and pin both official Pump and PumpSwap program contracts before any live proof.
This integration does not authorize a campaign, capacity above two in runtime,
or another selective-1h proof.

### Historical Candidate-Acquisition Foundation Clarification (Deferred)

The combined foundation audit, design, implementation, disposable migration
proof, and frozen offline capacity proof supersede the earlier exclusive-source
interpretation without rewriting its historical facts. Candidate discovery is
multi-source. Direct Pump/PumpSwap is first-class and mandatory for exact Pump
origin/graduation claims, but it is not the exclusive candidate universe.
DexScreener and GeckoTerminal may nominate candidates directly. The optional
free Birdeye Standard new-listing route may nominate only when an operator
supplies an account API-key secret reference; no paid fallback is allowed.
DEXTools remains deferred because a current exact free programmatic contract was
not established. PumpPortal foundation use is prohibited under its current
API-key/wallet contract. Aggregators cannot prove unsupported lineage or
canonical PumpSwap identity.

Non-Pump and unknown-origin candidates are not forced into Pump lineage. They
may remain eligible only with exact mint, supported token program, exact current
pool/pair and owner/program relationship, supported quote mint, fresh market,
age, holder, safety, liquidity, and tradeability evidence. Unknown origin stays
categorical. No source quota, preference, score, rank, confidence, or weighting
is permitted; source contribution is diagnostic only.

The implemented foundation is runtime-neutral. Generic N is
bounded to 16 for acquisition/reserve/selection mechanics, while approved active
Memory Factory capacity remains exactly two and the legacy projection rejects
manifests above two. This clarification authorizes no live source, RPC,
WebSocket, backfill, operational campaign, selective-1h proof, retrieval, or
financial capability. Post-foundation integration, transport-free proof,
pipeline repair, mint-identity admission repair, and durable cursor-to-live-range
repair are complete. The post-cursor-repair bounded live N2 proof is closed
BLOCKED on `IDENTITY_MERGE_FAILURE` after correct `FORWARD` bootstrap and
historical `BACKWARD` isolation; exact quote identity was absent for all four
candidates. N7 is `NOT_RUN`. The Pump migration observation decoupling
implementation/offline proof is closed PASS. Its bounded live N2 proof is
closed BLOCKED on `OPERATION_ACCOUNTING_MISMATCH`. The optional-global
operation-accounting repair and offline proof is closed PASS. The next
repaired-boundary live N2 proof is closed BLOCKED on honest
`OBSERVATION_ROW_CEILING` budget exhaustion after exact optional-global
accounting. The historical next task at that checkpoint was operator review of
that terminal closeout and redacted evidence; the restoration anchor above now
supersedes it. No automatic run, retry, successor, recovery, campaign, cursor
reset, N7, or later runtime lane is authorized.

V2-9 is closed PASS at commit 51bcfdb (`Close V2-9 four-hour proof lane`).
V2-9.7A through V2-9.7F are closed. V2-9.7F activation readiness is
`V2_9_7F_ACTIVATION_READINESS_PASS` (closeout:
`docs/printer-v1-v2-9-7f-activation-readiness-closeout.md`).
V2-9.8A is closed `V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS` (closeout:
`docs/printer-v1-v2-9-8a-operator-activation-gate-closeout.md`). The committed
PowerShell command is published but has not been run. V2-9.8B remains a
separate operator-run lane.

The Memory Growth Automation Audit and V2-0 current-state audit remain required supporting audit/readiness sources. They are not the active lane-order document.

The previous memory-growth build order remains historical for the X1-X14 era. It is not the active roadmap after V2-1 adoption.

Do not restart from V2-2A, V2-3, V2-4, V2-5, V2-6, V2-7, V2-8, or V2-9 unless the operator explicitly requests a historical audit.

Do not restart V2-9.7A–F unless the operator explicitly requests a historical audit.
Do not begin V2-10, V2-11, 1h/4h/12h/24h production work, retrieval, paper decisions, or any financial lane during V2-9.8B unless a later explicit lane authorizes them.

Every V2 major capability must follow this pattern:

- audit/readiness review
- design/specification
- implementation when applicable
- bounded proof/test
- closeout report

Every V2 lane must include Functionality Risks / Setbacks / Efficiency Blockers.

The post-V2-9 operational Memory Factory program must preserve bounded lifecycle continuation:

- discovery -> selection -> tracking -> governed collection
- conditional WINDOW_5M_MICRO_EVENT support
- main WINDOW_15M closeout
- standard hard-gated WINDOW_1H continuation for otherwise-valid activated tokens
- standard hard-gated WINDOW_4H continuation after a genuine eligible first-hour close
- automatic continuation stops at the WINDOW_4H checkpoint
- WINDOW_12H / WINDOW_24H remain selective and locked until later explicit lanes
- clean/dirty/blocked audit
- cooldown/archive
- candidate rotation
- persistent corpus reporting
- safe stop

The post-DTW100 standard-four-hour amendment removes behavior/outcome/learning-need qualification only from 15m->1h and 1h->4h observation. It does not weaken exact identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, or bounded-resource gates. `WINDOW_4H` real collection remains locked until its later explicit activation/rereadiness lane.

Do not track every timeframe for every token.

WINDOW_5M_MICRO_EVENT remains support-only. It may be conditionally captured for early pumps, dumps, wicks, traps, and exit realism, but it must be exact-linked to the token, pair, run, and main 15m lifecycle; remain Source-Governed and Scheduler-led; never become a main outcome memory; never replace 15m; never independently trigger continuation; stay excluded from main clean-memory thresholds; and never unlock retrieval or financial capabilities.

Memory-growth work must preserve all V1 restrictions:

- Solana-only
- Solana memecoin-only
- paper-trading only
- no live wallet
- no private keys
- no real funds
- no live execution
- no paid API dependency
- no scoring system
- no ranking system
- no confidence percentage system
- no weighted decision logic
- no engine bypassing Source Governor
- no engine bypassing Central Scheduler
- no paper decision without clean memory comparison
- no paper position without valid clean-memory-backed paper decision
- no dirty memory used for retrieval or decisions
- no BUY/SELL/HOLD unlock
- no positions
- no PnL

The following V2-9 observations were carried through the V2-9.7 program and
remain residual awareness items where not fully retired by later repairs:

- clean-promotion reporting under-count (partially repaired; remain report-honest)
- timeframe-confusing safety labels (timeframe-aware repairs landed; remain careful)
- transient heartbeat lock-file contention (lease repairs landed; remain monitorable)
- partial wallet-level flow authenticity
- missing embedded Git provenance (embedded provenance repairs landed; remain required)
- separate live report-only replay (zero-source report replay landed and live-proven)

<!-- PRINTER_V1_MEMORY_GROWTH_BUILD_ORDER_ANCHOR_END -->

## Assistant Active Build Order Anchor

For Claude, ChatGPT, Codex, and future assistant prompts, the assistant alignment anchor is:

- `docs/printer-v1-assistant-active-build-order-anchor.md`

This assistant anchor does not replace `AGENTS.md`.

It does not make the V2 build order the sole source of truth.

It confirms that the active memory-growth build order is:

- `docs/printer-v1-memory-growth-build-order-v2.md`

This build order is active inside the required source stack for Printer V1 memory-growth work.

The active memory-growth lane remains:

- `V2-9.8B — Active Bounded Memory Growth Operations`

V2-9.8A is closed PASS. V2-9.8B remains the active bounded operational Memory
Factory lane. It does not unlock retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, or PnL.

Within V2-9.8B, the operational factory active-path restoration supersedes the
candidate-acquisition prerequisite chain. Candidate foundation, N2/N7, global
Pump cursor, recovery and migration-observation admission code and evidence are
deferred, not deleted.

The 2026-08-26 four-token standard-4h source-stack adoption supersedes stale
restoration-only and 2026-08-01 wrapper-design next-lane pointers for current
authority. Current adopted envelope:

- two cycles;
- exactly two concurrently active token slots;
- up to four distinct token identities across the campaign;
- concurrent capacity remains exactly 2;
- standard `WINDOW_15M` → hard-gated `WINDOW_1H` → hard-gated `WINDOW_4H` → stop;
- `WINDOW_12H` / `WINDOW_24H` locked;
- no authorization is created by the adoption itself.

The exact current next permitted lane is:

```text
FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — STALE PRIOR AUTHORIZATION SEALED NON-REUSABLE
```

Historical at the time of the 2026-08-26 source-stack synchronization:
`POST-SYNCHRONIZATION FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS /
GOVERNANCE ONLY`. Later post-repair readiness, authorization-boundary design
PASS, independent package review PASS, and the stale exact-HEAD-drift closeout
supersede older pointers for current-lane selection; use the Active Authority
Stack and `CURRENT_HANDOFF.md`.

No automatic run, retry, recovery, successor, cursor reset, N7, provider/RPC
work, operational campaign, or Printer execution is authorized by this anchor
text alone. Stale authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46` is sealed
`STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION` and
governance-required non-reusable. Application/consumption remains blocked;
fresh preparation may begin only after this stale-closeout package is
committed and must stop again for independent package review.

## Printer V1 Python Builder Guide

For every Printer V1 Python implementation, repair, migration, runner,
scheduler, source adapter, report, test, or proof-tooling task, use
`docs/printer-v1-python-builder-guide.md` inside the active Printer V1 source
stack. It is not the sole source of truth and cannot override the active lane,
Clean Master Spec, active build order, approved designs, provider contracts,
Source Governor, Central Scheduler, or capability locks.

Before Claude, Codex, Grok, ChatGPT, or any future assistant suggests or
implements Python code for any blocker, bug, failing test, or live-proof failure,
it must perform the guide's Mandatory Source-Grounded Blocker Investigation and
classify the issue. Do not issue a repair prompt until the classification shows
that code is justified.

## V2-9.8B Post-Authoritative-Readiness Roadmap Anchor (2026-08-01) — HISTORICAL

Historical only. Preserved for provenance. Superseded for current next-lane
authority by the 2026-08-26 four-token standard-4h source-stack adoption:

- `docs/printer-v1-v2-9-8b-four-token-standard-4h-source-stack-adoption.md`

The repeated post-trust-boundary authoritative readiness audit is closed:

- commit: `21262837322b31301cbfc495f814d7f84f149774`
- verdict:
  `V2_9_8B_WINDOW_15M_REPEATED_POST_TRUST_BOUNDARY_REPAIR_AUTHORITATIVE_READINESS_AUDIT_PASS`

At that 2026-08-01 checkpoint the exact next permitted lane was:

```text
V2-9.8B WINDOW_15M External One-Shot Wrapper Manifest and Application Marker Design
```

That wrapper-design lane is no longer the current next lane. Wrapper/manifest/
marker construction and later standard-4h / four-token operational authority
advanced afterward and are now synchronized into the active source stack by the
2026-08-26 adoption above. No historical consumed authorization may be reused.

## V2-9.8B Four-Token Standard-4H Source-Stack Adoption Anchor (2026-08-26)

Current adopted operational envelope:

- `docs/printer-v1-v2-9-8b-four-token-standard-4h-source-stack-adoption.md`
- two cycles; exactly 2 concurrent active token slots; up to 4 distinct token
  identities across the campaign
- concurrent capacity remains exactly 2
- standard `WINDOW_15M` → hard-gated `WINDOW_1H` → hard-gated `WINDOW_4H` → stop
- `WINDOW_12H` / `WINDOW_24H` locked
- candidate-acquisition N2/N7/cursor/recovery deferred
- implemented capability ≠ previously exercised capability ≠ authorization now

The exact current next permitted lane is:

```text
FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — STALE PRIOR AUTHORIZATION SEALED NON-REUSABLE
```

Historical at the time of this adoption closeout:
`POST-SYNCHRONIZATION FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS /
GOVERNANCE ONLY`. Later post-repair readiness, authorization-boundary design
PASS, independent package review PASS, and the stale exact-HEAD-drift closeout
supersede older pointers for current-lane selection; use the Active Authority
Stack and `CURRENT_HANDOFF.md`.

This adoption creates no authorization, automatically authorizes no campaign,
and unlocks no live runtime. No existing consumed authorization,
`application_started.json`, campaign exit, terminal evidence, or historical
artifact may be reused as execution authority. Stale authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46` is sealed
`STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION` and
governance-required non-reusable. Application/consumption/execution remain
blocked; the post-commit lane is fresh exact-HEAD/exact-DB preparation only.

<!-- V2_9_8B_RETAINED_EVIDENCE_REPAIR_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Retained-Evidence Repair Closeout — Historical Authority

This current-state synchronization block supersedes earlier current-looking
V2-9.8B repair/readiness/next-sub-lane pointers in this document for the
retained-evidence repair chain. Historical lane text remains evidence only.

- implementation / bounded-proof baseline: `851d92627c3f5b05b1366af0d0dfef2712a330d8`
- authoritative DB SHA: `b273b47973b0b76edd6c131afd410764cf5c6d09e35c81ab565480c3bb587e07`
- bounded-proof verdict: `V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_BOUNDED_PROOF_PASS`
- closeout verdict: `V2_9_8B_RETAINED_EVIDENCE_PREFREEZE_ROLE_PROVENANCE_TIMING_REPAIR_CLOSEOUT_PASS`
- consumed authorization `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c` remains permanently non-reusable
- candidate-acquisition N2/N7 remains deferred and is not a prerequisite
- no Source Governor or Central Scheduler bypass
- successful freeze remains 4 candidates -> 2 selected + 2 report-only alternates
- standard memory path remains 15m -> 1h -> 4h -> stop
- 5m remains support-only; 12h/24h remain locked
- retrieval and all financial capability remain locked

At retained-evidence repair closeout time, the next permitted lane was:

`POST-CLOSEOUT FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS / GOVERNANCE ONLY`

That lane is readiness/governance only. It does not itself authorize issuance,
execution, providers, RPC/WebSocket, Scheduler ticks, or authoritative DB writes.

This retained-evidence repair pointer is historical after later readiness and campaign closeout.
<!-- V2_9_8B_RETAINED_EVIDENCE_REPAIR_CLOSEOUT_CURRENT_STATE_END -->

<!-- V2_9_8B_POST_CLOSEOUT_AUTH_READINESS_CURRENT_STATE_START -->
## V2-9.8B Post-Closeout Authorization Readiness — Historical Authority

Readiness verdict:

`V2_9_8B_POST_CLOSEOUT_FRESH_NEXT_BOUNDED_CAMPAIGN_AUTHORIZATION_READINESS_GOVERNANCE_PASS`

Audited closeout HEAD: `941ddd727b0e8b6aabf7eacbf9513f47979adb46`
Authoritative DB SHA: `b273b47973b0b76edd6c131afd410764cf5c6d09e35c81ab565480c3bb587e07`

The retained-evidence repair chain is closed. The historical authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260826T203834Z_c3063b7c` remains permanently non-reusable.

At readiness time, the next permitted lane was:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

That lane may prepare and independently review a fresh exact-HEAD/exact-DB
one-shot authorization artifact. It does not authorize Printer execution.
Any fresh authorization must bind to the new readiness commit HEAD produced by
this synchronization and to the exact DB SHA above. Separate operator approval
is still required before execution.

All permanent V1 locks remain unchanged.

This readiness pointer is historical after the later authorized campaign closeout.
<!-- V2_9_8B_POST_CLOSEOUT_AUTH_READINESS_CURRENT_STATE_END -->

<!-- V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Authorization 8e43eae7 Campaign Closeout — Current Authority

- campaign closeout: `V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_PASS`
- authoritative post-campaign DB: `f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`
- consumed authorization: `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
- campaign classification: `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- Cycle 1: 2 tokens; 15m clean-promoted; 1h dirty; 4h ineligible/no successors
- Cycle 2: `NO_PAIR / DURATION_EXHAUSTION`
- no current-campaign active work
- retrieval/financial/12h/24h locks remain closed

The exact current next permitted lane is:

`REMOTE HOST READINESS / PORTABILITY AUDIT ONLY — INFRASTRUCTURE SUPPORT; NO CAPABILITY ADVANCEMENT`

This is infrastructure audit support only. It does not advance the active
memory-growth capability build order and does not authorize deployment,
migration, authorization issuance, provider/RPC/WebSocket calls, Scheduler
execution, another campaign, retrieval, financial capabilities, or longer
windows.
<!-- V2_9_8B_AUTH_8E43EAE7_CAMPAIGN_CLOSEOUT_CURRENT_STATE_END -->

<!-- V2_9_8B_REMOTE_HOST_PAUSE_MEMORY_GROWTH_RETURN_CURRENT_STATE_START -->
## V2-9.8B Remote-Host Pause / Memory-Growth Return — Current Authority

Operator decision: remote-host / VPS work is paused while Printer continues the
local Mac V2-9.8B bounded memory-growth path.

Completed remote-host work remains preserved separately on
`agent/remote-host-linux-portability-implementation` at `f61419f2db37fc5eb220c20fafeaf15501218033`. It is not discarded, merged into this
lane, or treated as current operational authority.

This block supersedes older current-looking remote-host lane pointers in this
document for current-lane selection only. Historical remote-host evidence
remains valid evidence.

Current preserved campaign/data baseline:

- branch before this synchronization: `agent/v2-9-8b-aug25-a2z-repair-application`
- pre-synchronization HEAD: `fd558c9e8a691ee1963509d7488aef05908f93c7`
- authoritative DB: `data/printer_v1.sqlite3`
- authoritative DB SHA-256: `f4e54b3a2dc9f4dbd41b6f05bb5288f25ca15dc71b7e66de1e05ef7c213e34b1`
- consumed authorization:
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
- that authorization remains permanently non-reusable
- latest campaign classification remains
  `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- retrieval, financial capability, `WINDOW_12H`, and `WINDOW_24H` remain locked
- `WINDOW_5M_MICRO_EVENT` remains support-only

The exact current permitted lane is:

`POST-CAMPAIGN FRESH NEXT-BOUNDED-CAMPAIGN READINESS / GOVERNANCE ONLY`

This lane is read-only readiness/governance. It may establish exact final Git
identity, authoritative DB identity/health, tracked-tree cleanliness, runtime
quiescence, evidence continuity, and permanent-lock continuity.

It does not create or apply an authorization. It does not run Printer, contact
providers/RPC/WebSocket, run Central Scheduler, mutate the authoritative DB,
activate retrieval, activate financial capability, or unlock longer windows.

Only after a fresh exact-HEAD/exact-DB readiness PASS may the next separate lane
be considered:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

Separate operator approval remains required before any later one-shot execution.

Permanent V1 locks remain unchanged.
<!-- V2_9_8B_REMOTE_HOST_PAUSE_MEMORY_GROWTH_RETURN_CURRENT_STATE_END -->

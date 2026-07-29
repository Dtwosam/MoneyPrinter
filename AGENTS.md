# Printer V1 Build Rules



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

- Direct Pump.fun migration and PumpSwap state through approved free/public Solana RPC

- DexScreener

- GeckoTerminal

- PumpPortal optional governed launch/migration locator only after its authentication, wallet, free-versus-metered, and cost contract is resolved

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
- docs/printer-v1-v2-9-8b-candidate-acquisition-capacity-feasibility-audit.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-roadmap-adoption.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-combined-audit.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-complete-design.md
- docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-implementation-closeout.md

Historical previous active roadmap:

- docs/printer-v1-memory-growth-build-order.md

Historical proposal:

- docs/printer-v1-proposed-memory-growth-build-order.md

Current active memory-growth lane after V2-9.8A operator activation PASS:

- V2-9.8B — Active Bounded Memory Growth Operations

Inside V2-9.8B, the candidate-acquisition foundation roadmap adoption and the
combined foundation implementation are closed PASS. The Direct Pump/PumpSwap
contract audit, post-foundation integration, canonical live transport-owner
repair, and comprehensive pipeline repair are complete. The final post-repair
bounded live candidate-acquisition proof is closed
`V2_9_8B_FINAL_POST_REPAIR_BOUNDED_LIVE_CANDIDATE_ACQUISITION_PROOF_BLOCKED`
(closeout:
`docs/printer-v1-v2-9-8b-final-post-repair-bounded-live-candidate-acquisition-proof-closeout.md`).
The foundation mint-identity admission repair is closed PASS. The separately
authorized post-mint-repair `ACQUISITION_ONLY_N2` proof is closed
`V2_9_8B_POST_MINT_ADMISSION_REPAIR_LIVE_N2_PROOF_BLOCKED` (closeout:
`docs/printer-v1-v2-9-8b-post-mint-admission-repair-live-n2-proof-closeout.md`).
It ran exactly once and blocked before foundation admission on
`CURSOR_START_MISMATCH`; N7 is `NOT_RUN`. The exact next permitted task is an
operator decision on a separate source-grounded investigation lane for the
durable cursor-head to live proposed-start propagation boundary before any
repair or new live proof. It is not an operational Memory Factory campaign,
N2 retry, cursor reset, or N7 run.

Factory-wide candidate-acquisition authority is:

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

### Candidate-Acquisition Foundation Superseding Clarification (2026-07-29)

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
financial capability. Post-foundation integration, transport-free proof, and
pipeline repair and mint-identity admission repair are complete. The
post-mint-repair bounded live N2 proof is closed BLOCKED on
`CURSOR_START_MISMATCH` before foundation admission; N7 is `NOT_RUN`. The next
permitted task is only an operator-authorized source-grounded investigation
decision for the durable cursor-head to live proposed-start propagation
boundary before any repair or new live proof; no operational campaign, cursor
reset, N2 retry, or N7 run is authorized.

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

The post-V2-9 operational Memory Factory program must preserve selective continuation:

- discovery -> selection -> tracking -> governed collection
- conditional WINDOW_5M_MICRO_EVENT support
- main WINDOW_15M closeout
- selective WINDOW_1H continuation
- conditional WINDOW_4H continuation
- clean/dirty/blocked audit
- cooldown/archive
- candidate rotation
- persistent corpus reporting
- safe stop

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

The next active memory-growth lane is:

- `V2-9.8B — Active Bounded Memory Growth Operations`

V2-9.8A is closed PASS. V2-9.8B is the separately operator-run bounded
persistent 15m campaign lane. It does not unlock retrieval, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, or PnL.

Within V2-9.8B, the candidate-acquisition foundation, post-foundation
integration, transport-owner repair, pipeline repair, and mint-identity
admission repair are implemented and offline-proven. The post-mint-repair live
N2 proof is closed BLOCKED after exactly one run on `CURSOR_START_MISMATCH`
before foundation admission; N7 is `NOT_RUN`. The next permitted work is an
operator decision on a separate source-grounded investigation lane for the
durable cursor-head to live proposed-start propagation boundary before any
repair or new explicit live proof. It does not authorize cursor reset, N2
retry, N7, or the published operational Memory Factory campaign command.
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

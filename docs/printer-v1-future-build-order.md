# Printer V1 Future Build Order



Continuation after Phase 21 Controlled Operator Command Layer.



## Current V1 State After Phase 21



Printer V1 has completed Phase 0 through Phase 21.



Current checkpoints:



* Phase 0-20 checkpoint tag: `printer-v1-synthetic-checkpoint`

* Phase 21 commit: `Add controlled operator command layer`

* Persistent DB path: `data/printer_v1.sqlite3`

* DB state: `PERSISTENT_DB_EMPTY_SCHEMA_ONLY`

* Migrations applied: 001 through 020

* Real token rows: 0

* Real pair rows: 0

* Real source rows: 0

* Real snapshot rows: 0

* Real memory rows: 0

* Real retrieval rows: 0

* Real paper decisions: 0

* Real paper positions: 0

* Runtime started: false

* Memory started: false

* Paper trading started: false



Phase 21 added controlled one-shot operator commands for:



* DB initialization

* DB status

* DB counts

* migration status

* operator report

* synthetic validation

* readiness check



Printer is structurally built and operator-controllable, but it has not started learning from real Solana memecoin market data yet.



## Locked V1 Bans



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

* no engine bypassing the Source Governor

* no engine bypassing the Central Scheduler

* no paper decision without clean memory comparison

* no paper position without valid clean-memory-backed paper decision

* no memory without completed token evidence windows

* no dirty memory training decisions

* no broad context engine acting as a direct trade signal



Live trading is out of scope for V1.



Wallet/private-key/signing/transaction execution is out of scope for V1.



Real fund movement is out of scope for V1.



## Future Build Order Overview



The future path is:



Operator runbook

\-> source adapter contract

\-> one disabled free-source adapter

\-> one-shot real source smoke check

\-> controlled manual token/pair intake

\-> controlled real snapshots

\-> controlled context collection

\-> first real memory windows

\-> real memory audit

\-> real memory retrieval

\-> paper-only decisions

\-> simulated paper positions

\-> paper audit and operator review

\-> scheduler single-tick executor

\-> bounded multi-tick runtime

\-> long-run paper validation

\-> V1 paper release candidate



The goal is not to turn Printer into a live trading bot.



The goal is to move Printer from synthetic proof into controlled real-data paper operation without breaking the memory-first rules.



## Phase Permissions Matrix



### Planning and documentation only



* Phase 22



### Contracts and fixture-only source work



* Phase 23



### Real source adapter implementation, disabled by default



* Phase 24



### First real source fetch, source tables only



* Phase 25



### Real token/pair rows allowed



* Phase 26



### Real token snapshots allowed



* Phase 27



### Real context rows allowed



* Phase 28



### Real memory windows allowed



* Phase 29



### Memory audit only



* Phase 30



### Real memory retrieval allowed



* Phase 31



### Real-data paper decisions allowed



* Phase 32



### Simulated paper positions allowed



* Phase 33



### Paper audit and operator review allowed



* Phase 34



### Scheduler job execution allowed, one job only



* Phase 35



### Bounded multi-tick runtime allowed



* Phase 36



### Long-run paper validation allowed



* Phase 37



### Paper-only release candidate



* Phase 38



## Detailed Phase-by-Phase Plan



## Phase 22 - Future Build Order Anchor + Operator Freeze Runbook



Goal:



Create the repo-level future build order anchor and define the operator sequence, allowed commands, DB backup/checkpoint expectations, readiness checks, source limits, rollback procedure, and stop conditions.



Allowed:



* documentation only

* AGENTS.md anchor

* optional final build order note

* operator runbook text

* readiness policy text

* rollback policy text



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



* future roadmap exists in repo

* AGENTS.md tells Codex to read this doc before every phase after Phase 21

* Codex has a clear no-drift roadmap



## Phase 23 - Source Adapter Execution Contract



Goal:



Define adapter interfaces and Source Governor execution boundaries.



Allowed:



* adapter contracts/interfaces

* local fixture tests

* normalized response contracts

* source request recording behavior

* source response recording behavior

* source failure recording behavior

* rate-limit behavior

* stale-data behavior

* malformed-data behavior

* proof that adapters cannot bypass Source Governor



Not allowed:



* real HTTP fetching

* live source calls

* discovery runs

* token/pair writes from real data

* snapshots

* memory

* paper decisions

* positions

* runtime



Exit gate:



* adapter contract proves no source can bypass Source Governor

* adapters have no direct path into engines

* engines cannot call external sources directly



## Phase 24 - First Free Source Adapter, Disabled by Default



Goal:



Implement one real free-source adapter only, disabled by default.



Preferred first source:



* DexScreener



Important rule:



Do not build many adapters at once.



Do not implement GeckoTerminal, PumpPortal, CoinGecko, DefiLlama, GoPlus, Solana RPC, Helius, or Jupiter quote in this same phase unless explicitly requested in a later phase.



Allowed:



* one adapter

* fixture/mock tests

* disabled-by-default implementation

* Source Governor required

* no automatic execution



Not allowed:



* broad source adapter bundle

* live fetch by default

* discovery promotion

* token/pair writes

* snapshots

* memory

* paper decisions

* positions

* scheduler loop

* runtime



Exit gate:



* one adapter exists behind Source Governor

* adapter is disabled unless explicitly invoked

* fixture tests prove it records success/failure behavior correctly



## Phase 25 - One-Shot Real Source Smoke Check



Goal:



First phase allowed to fetch real data, but only by explicit operator command.



Scope:



* one source only

* one-shot command only

* limited source calls

* source tables only



Allowed:



* explicit operator command

* source request rows

* source response rows

* source failure rows

* source health report



Not allowed:



* token/pair creation

* discovery promotion

* snapshots

* memory

* paper decisions

* positions

* scheduler execution

* runtime



Exit gate:



* real source fetch works or fails honestly

* only source tables are affected

* failure does not create fake downstream data



## Phase 26 - Controlled Manual/Discovery Intake



Goal:



Begin real token/pair intake safely.



Start manual-first:



* operator-approved mint/pair input

* 1 to 3 tokens/pairs only



Only after manual intake works may controlled discovery intake be considered.



Allowed:



* token rows

* pair rows

* discovery audit rows

* tracking queue candidate rows

* scheduler enqueue-only jobs



Not allowed:



* snapshots unless explicitly queued for later phase

* memory

* paper decisions

* positions

* scheduler execution

* runtime



Exit gate:



* real token/pair rows can be created safely

* no downstream action is triggered accidentally

* tracking queue entries remain enqueue-only



## Phase 27 - Controlled Real Token Snapshot Collection



Goal:



Collect real token-level snapshots for explicitly approved tokens.



Scope:



* 1 to 3 tokens only

* fixed snapshot count

* fixed limited time window

* operator-approved only



Allowed:



* token snapshot rows

* snapshot coverage rows

* quality labels

* source request rows

* source response rows

* source failure rows



Not allowed:



* memory building

* paper decisions

* positions

* broad runtime

* scheduler execution loop



Exit gate:



* real snapshots exist

* snapshot quality can be audited

* incomplete windows remain incomplete

* token-level snapshots have priority over broad context



## Phase 28 - Controlled Real Context Collection



Goal:



Attach safety, liquidity/exit, trading flow, chart/volatility, micro-event, market regime, and Solana chain heat context to tracked tokens.



Allowed:



* governed source usage only

* context rows

* quality labels

* audit metadata



Not allowed:



* engine-owned direct source calls

* paper decisions

* positions

* runtime

* dirty memory promotion



Exit gate:



* tracked tokens have enough local evidence for memory-window review

* context rows are source-governed and audit-visible



## Phase 29 - First Real Memory Windows



Goal:



Build first real memory windows from completed real evidence.



Allowed:



* 15m window first

* later 1h/4h/12h/24h only after 15m path is proven

* episode rows

* outcome rows

* memory fingerprints



Rules:



* incomplete windows cannot become clean memory

* stale evidence cannot become clean memory

* missing critical context cannot become clean memory

* conflicting evidence cannot become clean memory

* dirty/audit-only memory cannot train decisions

* 5m micro-events cannot substitute for main memory windows

* no paper decisions yet



Exit gate:



* at least one real memory window is clean, dirty, partial, or audit-only for the correct reason

* dirty memory remains blocked from decision training



## Phase 30 - Real Memory Quality Audit



Goal:



Audit first real memory rows before retrieval or decisions.



Allowed:



* memory quality reports

* dirty-memory reason reports

* snapshot gap reports

* source-quality reports

* memory readiness review



Not allowed:



* force-cleaning memory

* paper decisions

* positions

* memory rewrites to hide dirty evidence



Exit gate:



* operator knows whether real memory is trustworthy

* dirty memory remains dirty

* clean memory has enough evidence to justify retrieval testing



## Phase 31 - Real Memory Retrieval



Goal:



Compare current setup to existing clean real memories.



Allowed:



* clean-memory retrieval only

* match labels

* match reasons

* audit-only retrieval reports



Not allowed:



* scores

* rankings

* confidence percentages

* vectors

* embeddings

* paper positions

* live trading



Exit gate:



* retrieval returns only clean eligible memory evidence

* retrieval does not promote dirty memory

* weak retrieval does not become a decision



## Phase 32 - Real-Data Paper Decision Activation



Goal:



Create paper-only decisions from real clean-memory retrieval.



Important initial rule:



At first, real-data decisions should allow only:



* NO_ACTION

* WAIT

* AVOID



BUY should remain disabled until a minimum clean-memory gate exists and is explicitly enabled by a later operator-approved rule.



Allowed:



* paper decision rows

* decision audit rows

* blocked decision rows



Not allowed:



* BUY without enough similar clean memory

* paper positions in this phase

* wallet/private-key/signing/transaction/live execution



Exit gate:



* Printer blocks weak setups

* Printer does not create BUY decisions without sufficient clean memory

* paper decisions are always memory-backed or blocked



## Phase 33 - Real-Data Simulated Paper Position Monitor



Goal:



Open and monitor simulated paper positions only from valid DECISION_ALLOWED + BUY paper decisions after BUY has been explicitly unlocked by memory gate.



Allowed:



* simulated paper positions

* simulated paper trade events

* simulated close events

* simulated PnL



Not allowed:



* real funds

* wallet

* private keys

* transaction building

* transaction signing

* transaction sending

* live execution



Exit gate:



* simulated positions only open from valid clean-memory-backed decisions

* no real execution path exists



## Phase 34 - Real Paper Audit + Operator Review



Goal:



Audit real-data paper decisions, positions, events, and simulated outcomes.



Allowed:



* paper audit reports

* operator review reports

* issue labels

* realism reports



Not allowed:



* rewriting memory

* rewriting decisions

* live trading path

* hiding bad outcomes



Exit gate:



* operator can see whether decisions were realistic, useful, or dangerous

* paper results are not treated as real profit unless exit realism is proven



## Phase 35 - Scheduler Single-Tick Executor



Goal:



First phase allowed to execute scheduler jobs.



Strict scope:



* execute at most one approved job

* then exit

* no loop

* no daemon



Allowed:



* one-shot scheduler execution command

* job lock

* job claim

* job execution

* job complete/fail

* audit trail



Not allowed:



* while True

* daemon

* background worker

* cron

* Celery

* APScheduler

* infinite runtime

* live trading



Exit gate:



* one scheduler job can execute safely without becoming a runtime

* resource priority order is respected

* failed jobs are recorded honestly



## Phase 36 - Bounded Multi-Tick Operator Runtime



Goal:



Introduce bounded runtime behavior.



Allowed:



* operator command with max jobs

* operator command with max seconds

* explicit stop conditions

* no daemon by default



Example command shape:



`printer-run-bounded --max-jobs N --max-seconds S`



Rules:



* operator sets N

* operator sets max seconds

* token snapshots and paper monitoring remain highest priority

* all source usage is governed

* no infinite loop

* no live trading

* runtime stops cleanly



Exit gate:



* Printer can run bounded paper-only operation

* Printer stops cleanly

* scheduler priority does not starve token snapshots or paper monitoring



## Phase 37 - Long-Run Paper Validation



Goal:



Run supervised paper-only validation using real free data.



Allowed:



* longer bounded operator sessions

* source health reporting

* memory quality reporting

* paper decision review

* paper monitor review

* paper audit review



Not allowed:



* live trading

* wallet/private keys

* real funds

* unbounded runtime

* unreviewed autonomous operation



Exit gate:



* Printer proves whether it can handle messy real Solana memecoin data

* memory quality is measurable

* paper decisions are audit-visible

* fake profits and exit realism failures are exposed



## Phase 38 - V1 Paper Release Candidate



Goal:



Freeze a complete paper-only V1 release candidate.



Requirements:



* governed source usage

* bounded scheduler

* clean memory growth

* memory-backed paper decisions

* simulated paper monitor

* paper audit

* operator reports

* no wallet

* no private keys

* no real funds

* no live execution

* no scoring system



Exit gate:



* Printer V1 is a complete paper-only Solana memecoin memory machine



## Source Adapter Activation Policy



Printer must never allow engines to call external sources directly.



Every source call must pass through:



1\. Source Governor

2\. source request recording

3\. source response or failure recording

4\. quality/staleness handling

5\. downstream engine consumption only after recorded evidence exists



Adapters must start disabled by default.



Only one adapter should be introduced first.



Broad adapter bundles are not allowed until the first adapter path proves safe.



## Runtime Activation Policy



Runtime must not appear before one-shot source, discovery, snapshot, context, memory, retrieval, paper decision, monitor, and audit paths have been proven.



Runtime activation order:



1\. no runtime

2\. one-shot operator commands

3\. one scheduler job, then exit

4\. bounded multi-tick command with max jobs and max seconds

5\. supervised long-run paper validation



No infinite loop belongs in early V1.



No daemon belongs in early V1.



No background worker belongs in early V1.



## Paper Decision Activation Policy



Paper decisions must remain blocked until clean memory retrieval exists.



Initial real-data decision activation should allow only:



* NO_ACTION

* WAIT

* AVOID



BUY should remain disabled until there is enough similar clean memory and an explicit operator-approved unlock rule.



Paper position creation must remain separate from paper decision creation.



A paper position can only open from a valid DECISION_ALLOWED + BUY decision.



No live wallet or real execution path may exist.



## Operator Commands and Safety Checks



Before moving into any future phase, operator should be able to run:



* `printer-readiness-check`

* `printer-db-status`

* `printer-db-counts`

* `printer-migration-status`

* `printer-operator-report`

* `printer-synthetic-validation`



Expected safe early state:



* readiness: `READY_SCHEMA_ONLY`

* DB state: `PERSISTENT_DB_EMPTY_SCHEMA_ONLY`

* migrations applied: 20

* real token rows: 0

* real snapshot rows: 0

* real memory rows: 0

* real paper decision rows: 0

* real paper position rows: 0

* memory_has_started: false

* paper_trading_has_started: false

* runtime_has_started: false



## Stop Conditions / Rollback Conditions



Stop immediately if any phase introduces:



* live trading

* wallet connection

* private keys

* transaction building

* transaction signing

* transaction sending

* real fund movement

* paid API dependency

* ungoverned source calls

* engine-owned source fetching

* scheduler loop before its phase

* runtime before its phase

* memory from incomplete evidence

* dirty memory training decisions

* paper decision without clean memory

* paper position without valid paper decision

* scores/rankings/confidence percentages

* vectors/embeddings

* web dashboard/frontend before explicitly approved



Rollback or patch immediately if:



* read-only commands mutate DB

* source smoke checks write token/pair rows

* discovery creates paper decisions

* snapshots create memory early

* retrieval uses dirty memory

* paper decisions ignore memory gates

* scheduler execution becomes a hidden loop

* runtime does not stop cleanly



## V1 End Rule



V1 ends as a paper-only system.



No live trading belongs in V1.



Any future live-trading idea must be treated as a separate future version after V1 proves realistic paper performance, clean memory growth, exit realism, and audited capital protection.




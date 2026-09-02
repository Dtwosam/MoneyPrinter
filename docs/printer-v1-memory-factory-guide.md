# Printer V1 Memory Factory Guide

## 0. Status and Authority

This document defines the future memory-growth policy for Printer V1.

It is a planning and source-of-truth guide for how Printer should grow clean Solana memecoin memory through bounded, scheduler-led, source-governed cycles.

This guide does not supersede:

- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-clean-master-spec.md`
- `AGENTS.md`
- `docs/printer-v1-final-build-order.md`
- `docs/printer-v1-future-build-order.md`

Authority order:

1. `AGENTS.md` remains the build discipline and restriction law.
2. `docs/printer-v1-clean-master-spec.md` remains the product/system law.
3. `docs/printer-v1-post-rc-build-order.md` remains the active post-RC roadmap after Phase 38.
4. This guide defines how future memory-growth work should behave once the roadmap reaches an approved memory-growth lane.

This guide does not authorize skipping active lanes.

This guide does not authorize runtime expansion, source fetching, operational memory growth, long-window collection, BUY unlock, paper positions, PnL, wallet logic, live trading, paid APIs, scoring, ranking, confidence systems, weighted decision logic, embeddings, vectors, or dirty-memory decisions.

Post-V2-9 status: V2-9 closed PASS at commit `51bcfdb`. No further 4h proof is required before operational readiness review, but operational memory growth remains locked until the active V2-9.7 program passes and the V2-9.8A operator activation gate is reached.

Manipulation-aware money-usefulness law: V2-9.7C.0A adopts
`docs/printer-v1-manipulation-aware-money-usefulness-product-law.md` as the
binding home for manipulation context, tradeable-path, and anti-hindsight
product laws. This guide follows that document by reference.

## 1. Purpose

Printer V1 is a Solana-only memecoin memory and paper-trading machine.

The Memory Factory is the bounded process that grows Printer's clean memory by tracking Solana memecoins, recording what happens across evidence windows, auditing clean versus dirty data, and storing only valid completed memories for future comparison.

The Memory Factory exists because Printer cannot make useful paper BUY, SELL, or HOLD decisions until it has enough clean completed memories from many tokens and many market conditions.

Printer must first learn what happened before it can decide what should happen now.

The Memory Factory should help Printer learn:

- which pumps were tradable
- which pumps were traps
- which exits were realistic
- which exits were fake chart profit
- which holds round-tripped
- which waits saved money
- which waits missed opportunity
- which avoids protected capital
- which avoids missed real upside
- which tokens died quickly
- which tokens revived
- which liquidity conditions mattered
- which flow conditions mattered
- which chart structures mattered
- which market/Solana context mattered

## 2. Locked V1 Rules

Printer V1 remains:

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
- no memory without completed token evidence windows
- no dirty memory training decisions
- no broad context engine acting as a direct trade signal
- no vectors/embeddings unless explicitly approved later as out-of-scope for V1

Live trading is out of scope for V1.

Wallet/private-key/signing/transaction execution is out of scope for V1.

Real fund movement is out of scope for V1.

The Memory Factory must not weaken these restrictions.

## 3. Memory Factory Definition

The Memory Factory is not one engine making decisions.

It is an operator-approved, bounded workflow that coordinates existing Printer components:

```text
operator starts bounded cycle
-> direct Pump/PumpSwap candidate acquisition
-> market enrichment and categorical admission
-> selection
-> tracking
-> governed collection
-> conditional WINDOW_5M_MICRO_EVENT support
-> main WINDOW_15M closeout
-> standard hard-gated WINDOW_1H continuation
-> standard hard-gated WINDOW_4H continuation
-> clean/dirty/blocked audit
-> cooldown/archive
-> candidate rotation
-> persistent corpus reporting
-> safe stop
```

The Memory Factory must be:

- bounded
- operator-approved
- scheduler-led
- source-governed
- audit-first
- clean-memory-only for retrieval
- dirty-memory-preserving for audit
- paper-only
- non-autonomous for money decisions
- unable to unlock BUY by itself
- unable to open paper positions by itself
- unable to create PnL by itself
- unable to activate retrieval by itself
- unable to start before the active V2-9.8A gate

## 4. Why Memory Factory Comes Before Paper Trading Expansion

Printer's future paper trading side depends on memory.

Paper BUY, SELL, and HOLD decisions only become meaningful when Printer can compare a current token setup against enough clean historical memories.

Before Printer can say:

```text
BUY: this setup resembles past clean setups that pumped with realistic entry and exit.
```

or:

```text
SELL: this setup resembles past clean setups that dumped, round-tripped, or lost exit liquidity.
```

it must first have enough clean memories of:

- pumps
- dumps
- fake pumps
- fast pump-dumps
- wick pumps
- late-buy traps
- consolidations
- liquidity decay
- revivals
- dead tokens
- correct avoids
- wrong avoids
- correct waits
- wrong waits
- round-trips
- realistic profits
- unrealistic profits
- late entries
- missed entries
- exit failures

Therefore, memory growth is not optional. It is the foundation of the whole Printer system.

## 5. Future Operator Command Shape

Future Memory Factory work should eventually expose a small set of operator commands.

These examples are guide targets only. They do not mean the commands currently exist.

### Start a bounded memory cycle

```powershell
printer-run-memory-factory-cycle `
  --operator-approved `
  --mode conservative `
  --duration 6h `
  --max-active-tokens 10 `
  --max-new-tokens 50 `
  --windows 5m,15m,1h `
  --db-path data\printer_v1.sqlite3
```

### Check current status

```powershell
printer-memory-factory-status `
  --db-path data\printer_v1.sqlite3
```

### Produce a cycle report

```powershell
printer-memory-factory-report `
  --since 24h `
  --db-path data\printer_v1.sqlite3
```

### Stop a bounded cycle safely

```powershell
printer-stop-memory-factory-cycle `
  --operator-approved `
  --db-path data\printer_v1.sqlite3
```

The first implementation should prefer a bounded cycle command over an unbounded daemon.

No Memory Factory command may bypass Central Scheduler or Source Governor.

## 6. Token Selection Policy

Discovery is intake, not alpha.

Printer should not track only tokens that look bullish. Printer must grow a balanced memory dataset that includes winners, losers, traps, dead tokens, and ambiguous cases.

### Token states

Memory Factory may classify discovered candidates as:

- `INSTANT_REJECT_MEMORY_ONLY`
- `IGNORE`
- `WATCH_ONLY`
- `TRACK_NORMAL`
- `TRACK_FAST`
- `LONG_WINDOW_CANDIDATE`
- `ARCHIVED`

### Selection principle

Token selection should be based on learning value, source quality, and evidence usefulness.

Learning value includes:

- strong pump behavior
- failed pump behavior
- sudden dump behavior
- wick-only pump
- micro-pump
- late-buy trap
- liquidity rising
- liquidity falling
- liquidity removed
- volume rising
- volume decaying
- transaction spike
- transaction decay
- consolidation
- revival
- dead token behavior
- hot pair behavior
- migration behavior
- suspicious safety behavior
- clean avoid behavior
- wrong avoid behavior
- realistic exit behavior
- unrealistic exit behavior

### What Printer must avoid

Printer must avoid building a winner-only dataset.

A winner-only dataset would teach Printer to chase pumps and ignore the many tokens that fail, trap, or become untradeable.

Printer needs both profit memory and protection memory.

## 7. Tracking Lane Policy

### WATCH_ONLY

Purpose:

- light monitoring
- wait for useful activity
- avoid wasting snapshot capacity

Suggested behavior:

- refresh every 20-30 minutes
- do not open main memory unless promoted
- promote only if liquidity/activity/source quality improves

Promotion examples:

- valid pair appears
- liquidity appears
- migration happens
- volume and txns start
- token revives
- consolidation becomes useful

### TRACK_NORMAL

Purpose:

- normal memory growth
- active but not explosive token behavior

Suggested behavior:

- first 15m snapshots every 5-10 minutes
- open 15m main memory
- continue through the first hour and to the 4h checkpoint when hard operational/evidence gates remain valid; outcome or learning-need labels do not qualify continuation
- cadence may slow after the opening period according to the approved Scheduler policy, but observation does not stop merely because activity fades

### TRACK_FAST

Purpose:

- high-detail memory for fast-changing tokens

Suggested behavior:

- first 15m snapshots every 1-3 minutes if source capacity allows
- open 5m support evidence
- open 15m main memory
- continue through the first hour and to the 4h checkpoint when hard operational/evidence gates remain valid; survival, outcome, or learning-need labels do not qualify continuation
- speed up around dumps, liquidity decay, revival, or exit danger when the approved Scheduler policy allows

TRACK_FAST is not a BUY signal.

### LONG_WINDOW_CANDIDATE

Purpose:

- longer lifecycle learning after early evidence exists

Suggested behavior:

- applied only after the standard 4h checkpoint for later long-horizon learning
- eligible for future 12h or 24h tracking only in their separately approved selective lanes
- not every token proceeds beyond 4h
- prioritize later-horizon lessons such as survival, revival, delayed dump, or full-cycle outcomes without turning the category into a score or ranking

### ARCHIVED

Purpose:

- stop spending resources on tokens with completed useful windows or no further tracking value

Suggested behavior:

- keep memory/audit records
- do not refresh unless revival or new source evidence appears

## 8. Timeframe Activation Policy

Printer supports these evidence windows:

- `WINDOW_5M_MICRO_EVENT`
- `WINDOW_15M`
- `WINDOW_1H`
- `WINDOW_4H`
- `WINDOW_12H`
- `WINDOW_24H`

### WINDOW_5M_MICRO_EVENT

Role:

- support-only evidence
- fast pump/dump behavior
- wick-only move
- late-buy trap
- tradable micro-pump
- untradable micro-pump
- micro-exit realism
- held-to-15m result
- lifecycle-wide support event during an ongoing 15m, 1h, or 4h lifecycle

5m must not:

- become a main outcome memory
- replace 15m
- independently trigger 1h, 4h, 12h, or 24h continuation
- count toward main clean-memory thresholds
- determine cooldown, archive, or reopen by itself
- unlock retrieval by itself
- unlock paper decisions
- unlock BUY
- unlock SELL, HOLD, WAIT, or AVOID
- open paper positions
- create trade events
- create paper trade audits
- create PnL

5m may be conditionally captured for early pumps, dumps, wicks, traps, liquidity
shocks, reversals, failed breakdowns, reclaims, entry traps, exit-realism
events, and rapid flow changes after V2-9.7C approves exact categories. It must
be exact-linked to campaign, run, token, pair, root 15m lifecycle, containing
main window, exact triggering snapshots, source provenance, and scheduler work;
remain Source-Governed and Central-Scheduler-led; and stay support-only.

5m may inform a later main memory window.

5m must not be restricted to the opening portion of a token lifecycle. It can be
support evidence anywhere inside an ongoing 15m, 1h, or 4h lifecycle, but it
remains non-authoritative for main outcomes.

### WINDOW_15M

Role:

- first main outcome memory
- base memory-growth window
- fastest useful main outcome layer

15m should be the first real Memory Factory target.

### WINDOW_1H

Role:

- short-term continuation/failure memory
- shows whether 15m move survived or failed

1h should start after 15m factory behavior is stable.

### WINDOW_4H

Role:

- medium-term behavior
- shows whether the token survived beyond the first hype cycle

Under the post-DTW100 standard-four-hour policy and the 2026-08-26 four-token
standard-4h source-stack adoption, every otherwise-valid activated token with a
genuine eligible first-hour predecessor continues to the 4h checkpoint under the
adopted operational envelope. Outcome and learning-need labels do not qualify
that continuation. Automatic continuation stops at 4h; `WINDOW_12H` /
`WINDOW_24H` remain locked. Source-stack adoption of this lifecycle does not by
itself create authorization or start a campaign.

### WINDOW_12H

Role:

- survival
- delayed dump
- revival
- longer consolidation
- slower liquidity decay

12h should start after 4h is reliable.

### WINDOW_24H

Role:

- full-day outcome memory
- full-cycle pump/dump/revival/death behavior
- stronger sell/hold lessons

24h should be last because it is slow, expensive, and capacity-heavy.

### Activation stages

Memory Factory should activate windows in this order:

1. 15m main memory + 5m support evidence
2. 1h continuation/failure memory
3. 4h medium-term memory
4. 12h survival/revival/delayed-dump memory
5. 24h full-cycle memory

Do not activate all timeframes at once. The adopted bounded observation lifecycle is standard through the 4h checkpoint for otherwise-valid activated tokens: 15m and 1h outcome/learning-need labels do not decide whether observation continues. Hard evidence-quality, exact-identity, freshness, provenance, safety, continuity, Source Governor, Central Scheduler, cancellation, and bounded-resource gates still apply. Automatic continuation stops at 4h; 12h and 24h remain selective and locked until later explicit lanes.

No timeframe is an action trigger. WINDOW_5M_MICRO_EVENT, WINDOW_15M,
WINDOW_1H, WINDOW_4H, WINDOW_12H, and WINDOW_24H are evidence and outcome
horizons only. A window kind must not independently cause an action,
continuation, retrieval activation, position, trade event, paper audit, or PnL.

## 9. Snapshot Frequency Policy

Suggested snapshot frequencies are planning defaults. Final values should be configurable and controlled by Central Scheduler.

### TRACK_FAST first 15m

- every 1-3 minutes if free-source limits allow
- force close snapshot near 5m and 15m window close

### TRACK_FAST until 1h

- every 3-5 minutes after first 15m if token remains active

### TRACK_FAST until 4h

- every 5-10 minutes if token remains relevant

### TRACK_NORMAL first 15m

- every 5-10 minutes

### TRACK_NORMAL until 1h

- every 10-15 minutes

### TRACK_NORMAL until 4h

- every 15-30 minutes if still useful

### WATCH_ONLY

- every 20-30 minutes
- speed up only if activity appears

### Window-close rule

Printer should prioritize final snapshots near each memory-window close.

A clean memory window should not be created if the window-close evidence is missing or too stale.

## 10. Source Roles and Limits

All source access must go through Source Governor.

No engine may create its own API loop.

Source limits and API behavior may change. Before implementation, re-check official source docs and keep budgets configurable.

### Historical deferred candidate-acquisition authority

The preserved but deferred candidate-acquisition foundation adoption is
`docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-roadmap-adoption.md`.
Its subsystem-local historical authority is:

1. direct Pump on-chain evidence for exact launch origin;
2. direct Pump migration plus exact PumpSwap evidence for graduation and
   canonical pool identity;
3. DexScreener and GeckoTerminal for direct candidate nomination and their
   supported current market, liquidity, activity, age, and coverage facts;
4. approved Solana RPC providers for exact on-chain transport and verification;
   and
5. PumpPortal only as an optional governed locator after its authentication,
   wallet, free-versus-metered, and cost contract is resolved.

Aggregator observations must never replace exact Pump origin or exact joined
Pump-migration/PumpSwap graduation evidence. The integrated acquisition owner must
be Source-Governed and Scheduler-led and must provide both bounded finalized
live observation and restart-safe, cursor-based historical backfill for missed
Pump creation and migration events. Live and backfill are two modes of one owner,
not independent source loops.

Unknown or unsupported Pump/PumpSwap instruction, event, account, quote-mint,
extension, PDA, or pool layouts fail closed. Before a live proof, retain the
refreshed and pinned exact official Pump and PumpSwap repository commit, raw artifact hashes,
program IDs, supported instruction/account/event contracts, discriminators,
canonical-pool rules, and fixtures. Cursor advancement must stop before any
unresolved observation.

The combined audit/design/implementation/offline-proof lane supersedes the
earlier exclusive-source interpretation. Discovery is multi-source:
DexScreener and GeckoTerminal may nominate directly, optional free Birdeye
Standard new listings may nominate with an operator-supplied account API key,
and direct Pump/PumpSwap remains mandatory only for exact Pump-specific claims.
Non-Pump and unknown-origin candidates may use the exact-present-pool branch.
DEXTools is deferred and PumpPortal foundation use is prohibited under the
current contract. No source weighting or quota exists.

The integrated owner is runtime-neutral and transport-free proof is complete.
The final post-repair bounded live acquisition proof is closed BLOCKED: Stage A
`ACQUISITION_ONLY_N2` once with `IDENTITY_MERGE_FAILURE`, Stage B
`ACQUISITION_ONLY_N7` `NOT_RUN`. That former next-lane pointer is superseded by
the operational factory active-path restoration. This guide does not authorize
N2 retry, N7, the operational Memory Factory campaign, runtime capacity above
two, or another selective-1h proof.

The following Direct Pump/PumpSwap foundation role descriptions apply only to
the deferred subsystem. They are not an active factory prerequisite, cursor
authority, recovery authority or migration-observation admission gate.

### Pump.fun / Pump Program

Role:

- required exact launch-origin authority;
- required exact migration-instruction authority;
- bounded finalized live-tail and cursor-backfill observation only through the
  future adopted shared owner; and
- no wallet, signing, transaction submission, trade stream, or execution.

### PumpSwap / Pump AMM

Role:

- required exact graduation and canonical-pool authority when joined to exact
  Pump migration evidence;
- exact program ownership, Pool account, mint, quote mint, canonical index,
  PDA, and adopted layout verification; and
- never a substitute for the Pump migration transaction by account presence
  alone.

### DexScreener

Role:

- current market visibility and coverage enrichment
- primary pair snapshot source
- token profiles
- boosted/latest token context
- liquidity, volume, FDV, price change, txns where available

Use carefully with per-endpoint budgets.

### GeckoTerminal

Role:

- current market visibility and coverage enrichment
- backup market confirmation
- OHLC/liquidity/volume confirmation
- lower-frequency only

Do not use GeckoTerminal as a high-frequency primary source unless source limits and configuration explicitly allow it.

### PumpPortal

Role:

- unavailable as candidate authority under the current unresolved contract;
- optional future governed locator for new-token and migration observations
  only after a separate official contract adoption passes.

V1 must not depend on metered trade/account streams, wallet-linked funding, or
paid usage. PumpPortal observations, if later adopted, must be independently
verified through direct Pump/PumpSwap evidence and cannot satisfy a mandatory
origin or graduation fact.

### Jupiter Quote

Role:

- paper entry/exit realism
- slippage/price-impact/route quote checks where appropriate

Jupiter must never be used for execution in V1.

### Solana RPC / Helius free tier

Role:

- limited confirmation
- mint/account/pool checks
- safety verification where needed

Use only through Source Governor with strict budgets.

### CoinGecko / Alternative.me / DefiLlama

Role:

- market regime context
- SOL/BTC/ETH context
- Solana chain heat context
- broad liquidity/volume environment

These are context sources, not token-level trade signals.

## 11. Source Budget and Priority Policy

When resources, rate limits, or scheduling capacity are tight, Printer should prioritize:

1. Open paper-trade monitoring, once paper positions are allowed
2. Exit-risk token snapshots
3. TRACK_FAST / micro-event token snapshots
4. TRACK_NORMAL token snapshots
5. Memory-window close snapshots
6. Safety and liquidity refreshes
7. Discovery refresh
8. Market regime context
9. Solana chain heat context
10. Backup checks

For current V1 memory-growth lanes where paper positions remain locked, the practical priority becomes:

1. TRACK_FAST / micro-event token snapshots
2. TRACK_NORMAL token snapshots
3. Memory-window close snapshots
4. Safety and liquidity refreshes
5. Discovery refresh
6. Market regime context
7. Solana chain heat context
8. Backup checks

## 12. Clean Memory Requirements

A main memory window is clean only if:

- full duration completed
- enough snapshots were collected
- critical fields exist
- critical sources are not failed/stale
- source_status and data_quality_label support clean use
- market regime context is attached or explicitly recorded as acceptable/known missing under current policy
- Solana chain heat context is attached or explicitly recorded as acceptable/known missing under current policy
- safety state is available or missing status is honestly recorded
- liquidity/exit state is available where relevant
- trading flow/chart evidence is available where relevant
- outcome label is clear
- memory quality is assigned
- entry/exit realism is known where profit is claimed
- memory can explain what action worked, failed, protected capital, caused loss, missed upside, or round-tripped

A window must not become clean just because the token pumped.

Clean memory is evidence quality plus outcome clarity, not price performance.

## 12A. Manipulation-Aware Money-Usefulness Guidance

Use `docs/printer-v1-manipulation-aware-money-usefulness-product-law.md` as the
binding source for these operating rules.

Manipulation context is not the same thing as evidence quality. A token that
appears manipulated, coordinated, artificial, concentrated, or authenticity-weak
may still produce clean memory when the observations are complete, timely,
exact-target, Source-Governed, Scheduler-led, and realistically interpretable.
The manipulation condition must be preserved as market-integrity context, not
converted into automatic rejection or automatic authorization.

Full-window outcome and internal trade-opportunity outcome are separate layers.
A negative 15m, 1h, or 4h window can still contain useful internal opportunity
segments, such as early expansion, valid hold, correctly avoided late chase,
correct exit, missed upside, or failed re-entry. Those internal segments must
not rewrite the full-window outcome.

Chart profit is not executable profit. Observed peaks, ATHs, and wick highs are
chart facts until event-time route, liquidity, slippage, price impact, duration,
and exit evidence prove realistic capturability. Missing quantitative execution
evidence must remain unknown or unproven.

Wallet and participant authenticity remains `UNKNOWN` when unproven. Partial
flow labels, holder concentration, or activity bursts must not be presented as
proof of genuine participants, related-wallet clusters, or coordinated accounts
unless a governed source supplies that exact evidence.

Checkpoint anti-hindsight is mandatory. A checkpoint may use only facts
available at that time, with finite predeclared action paths. Later outcomes may
evaluate an earlier checkpoint but must never rewrite it, invent an exact-bottom
entry, invent an exact-top exit, or reconstruct a completed-chart action path.

`WINDOW_5M_MICRO_EVENT` remains permanently support-only and non-authoritative.
It may explain early pumps, dumps, wicks, traps, and exit realism only when
exact-linked to the token, pair, run, scheduler work, and containing main
lifecycle. It never replaces 15m, independently triggers continuation, counts
toward main clean-memory thresholds, unlocks retrieval, or unlocks financial
capability.

Optional operator capital policy is future paper-research policy only. It can
never disable permanent Printer invariants such as Source Governor, Central
Scheduler, clean-memory requirements, safety gates, paper-only mode, no live
funds, no dirty-memory decisions, no scoring, and no hidden weighted logic.

## 13. Dirty and Audit Memory Rules

Dirty memory is useful for audit but never for decisions.

Dirty or audit-only reasons include:

- missing critical fields
- stale data
- failed source
- conflicting data
- incomplete window
- snapshot gaps too large
- missing close snapshot
- untradeable token
- broken pair data
- unknown critical safety state
- unknown liquidity/exit realism when profit is claimed
- unrealistic profit
- fake chart profit
- 5m-only evidence trying to act as main memory
- context mismatch
- source conflict
- scheduler gap
- Source Governor failure
- DB/write failure

Dirty memory must remain stored for audit history.

Old dirty memory must not block newer completed evidence.

Dirty memory must not support BUY, SELL, or HOLD.

Dirty memory may support future system-quality audits and data-collection improvements.

## 14. Expected Memory Yield Targets

These are planning ranges, not promises.

Clean-memory yield matters more than total rows.

### Conservative first version

Suggested setup:

- duration: 6h
- max new tokens/day: 30-50
- accepted tracking/day: 8-15
- max active at once: 10
- max TRACK_FAST: 3
- max TRACK_NORMAL: 7
- WATCH_ONLY limit: 20-40
- windows: 5m support + 15m main
- 1h: only after clean 15m and approved policy

Expected clean output:

- clean 5m support/day: 5-15
- clean 15m/day: 3-8
- clean 1h/day after enabled: 1-4
- clean 4h/day after enabled: 0-2
- clean 12h/day after enabled: 0-1
- clean 24h/day after enabled: 0-1

### Stable later version

Suggested setup:

- max new tokens/day: 100-200
- accepted tracking/day: 20-40
- max active at once: 20-30
- staged windows enabled through 1h/4h/12h/24h only after approval

Expected clean output:

- clean 15m/day: 10-25
- clean 1h/day: 5-15
- clean 4h/day: 2-8
- clean 12h/day: 1-4
- clean 24h/day: 1-3

### Interpretation

A day with 5 clean well-audited memories is better than a day with 50 dirty weak records.

The operator report must separate:

- discovered tokens
- active tracked tokens
- windows attempted
- clean memories
- dirty/audit-only memories
- retrieval-eligible memories

## 15. Stop Conditions

A Memory Factory cycle must stop, degrade, or require operator review if:

- source failure rate exceeds configured threshold
- suggested first threshold: 40%
- snapshot gap rate exceeds configured threshold
- suggested first threshold: 30%
- Source Governor detects repeated stale data
- DB locks or write failures appear
- Central Scheduler queue falls behind badly
- dirty ratio becomes extreme
- source budget is exhausted
- window-close snapshots are repeatedly missed
- any path tries to create BUY unexpectedly
- any path tries to create paper positions unexpectedly
- any path tries to create PnL unexpectedly
- any engine bypasses Source Governor
- any engine bypasses Central Scheduler
- data quality labels are missing on critical records
- clean memory would be created from incomplete evidence
- dirty memory appears in retrieval or decision support

A stopped cycle is acceptable if it prevents memory pollution.

## 16. Operator Report Requirements

Every Memory Factory cycle report must include:

### Cycle summary

- cycle_id
- started_at
- ended_at
- duration
- mode
- operator_approved
- db_path
- windows enabled
- max token limits

### Discovery

- tokens discovered
- tokens rejected
- tokens ignored
- tokens watch-only
- tokens track-normal
- tokens track-fast
- long-window candidates
- archived tokens

### Source quality

- source requests by source
- source failures by source
- stale data count
- missing critical data count
- rate-limit events
- fallback usage
- source_failure_rate

### Snapshot quality

- snapshots planned
- snapshots collected
- snapshots missed
- close snapshots collected
- close snapshots missed
- snapshot_gap_rate
- data-quality breakdown

### Memory output

- windows opened by kind
- windows closed by kind
- clean memories by kind
- partial/audit memories by kind
- dirty memories by kind
- do_not_train memories by kind
- retrieval-eligible memory count
- non-retrieval memory count

### Outcome labels

- pumps
- dumps
- fake pumps
- fast pump-dumps
- late-buy traps
- wick pumps
- consolidations
- revivals
- dead tokens
- liquidity decay
- exit unrealistic
- correct avoid
- wrong avoid
- correct wait
- wrong wait
- round-trip
- realistic profit
- unrealistic profit

### Locked state

- BUY unlock status
- paper position status
- PnL status
- live execution status
- wallet/private-key status
- paid API dependency status

For V1 memory-growth reports, these must remain locked/false unless a later approved lane explicitly changes the paper-only gates.

## 17. Anti-Bias Rules

Printer must avoid building a misleading dataset.

### No look-ahead bias

No future snapshot may support a past decision.

A decision can only use data available at or before the decision timestamp.

Outcome labels are assigned only after the window closes.

Historical decision checkpoints must be constructed from the evidence available
at that checkpoint only. Later recovery, observed high, collapse, final close,
or outcome label can evaluate the checkpoint but cannot justify the checkpoint's
simulated action.

### Full trajectory, not just close

Main memories must preserve the full intra-window path where evidence permits:
opening state, expansions, pullbacks, breakdowns, recoveries, reclaims,
consolidations, second expansions, peak failures, collapses, and final outcome.
The exact phase vocabulary must be approved and categorical; runtime must not
invent labels dynamically.

The factory should preserve opening price, observed high and low, closing price,
time to high and low, favorable and adverse excursion, drawdowns, recovery,
range width, reversal count and order, time above and below opening, snapshot
color counts, higher-high/lower-low behavior, phase-level liquidity, volume,
transactions, flow, safety changes, and entry/exit realism where sources support
them. Unsupported facts remain UNKNOWN or UNPROVEN.

### Conditions, not nominal prices

Future comparisons must use current setup evidence: path and reversals,
liquidity, entry and exit realism, volume, transactions, trading flow, safety,
volatility, market context, Solana context, time since prior expansion or
collapse, current position state, and similar historical checkpoint outcomes.

Printer must not match across tokens by nominal price alone. The prohibited
reasoning is: past token recovered from price X, current token reached price X,
therefore BUY.

### Realistic action paths and re-entry

When later paper-decision lanes explicitly unlock decision evaluation, each
approved scheduled snapshot and material market event must rebuild the current
setup and evaluate BUY, SELL, HOLD, WAIT, AVOID, and NO_ACTION eligibility
against clean historical checkpoint memories.

A token may eventually produce multiple separate paper trades inside one longer
tracked lifecycle, but every re-entry requires a closed previous position, a
fresh setup, a new clean-memory comparison, new entry and exit realism checks,
new invalidation and exit conditions, no future information, and a separately
auditable paper decision and result. This guide does not unlock those
capabilities.

### Observed peak versus capturable exit

Observed highs are chart facts. They are not automatically paper profit.
Realistically capturable exits require event-time evidence: usable liquidity,
valid paper route or quote, acceptable slippage and price impact, sufficient
opportunity duration, no hidden snapshot gap, no wick-only assumption, and a
valid exit rule at that checkpoint. Otherwise the capturable exit remains
UNKNOWN or UNPROVEN.

### No winner-only memory

Printer must store winners, losers, traps, dead tokens, wrong avoids, and wrong waits.

### No survivorship bias

Dead tokens and rejected tokens are useful memory.

If Printer only remembers tokens that survived, it will overestimate upside and underestimate failure.

### No perfect-top exits

Printer must not assume it sold the top unless a real snapshot, quote, and exit rule support that timing.

### No fake chart profit

A chart pump is not clean profit if entry or exit was unrealistic.

### No dirty-memory decision support

Dirty, stale, incomplete, failed, or do_not_train memory must not support BUY, SELL, or HOLD.

### No score drift

Printer must not convert memory into scores, ranks, weighted outputs, or percentage certainty.

Memory comparison can describe matching conditions, similar outcomes, conflicts, best historical action, and worst historical action.

## 18. Paper Decision Readiness Gates

The Memory Factory does not unlock BUY.

Paper decision readiness should grow in stages:

### Stage A — WAIT / AVOID / NO_ACTION

Allowed earliest because these protect against weak memory or weak data.

These decisions still require clean-memory-aware reporting and operator gates.

### Stage B — BUY review readiness

BUY should not be reviewed seriously until Printer has enough clean 15m and 1h memory to compare current setups meaningfully.

Planning-only thresholds:

- 50-100 clean 15m memories before serious BUY unlock review
- 30+ clean 1h memories before continuation behavior is trusted
- clean avoid/wait examples must exist, not only pump examples
- exit realism examples must exist

### Stage C — Paper BUY unlock

BUY requires a separate future operator-approved BUY unlock lane.

This guide does not authorize BUY unlock.

### Stage D — Paper position readiness

Paper positions should not reopen until:

- valid clean-memory-backed BUY exists
- safety is acceptable
- entry is realistic
- exit is realistic
- paper size bucket is defined
- invalidation condition exists
- monitoring cadence can protect exits
- position audit path is ready

### Stage E — SELL/HOLD readiness

SELL and HOLD only matter after a paper position exists.

SELL/HOLD must be based on:

- current position state
- similar clean memories
- liquidity/exit danger
- flow flip
- safety change
- chart exhaustion/breakdown
- invalidation condition
- realistic exit quote/snapshot timing

## 19. Roadmap Placement

This guide now follows the active post-V2-9 memory-growth roadmap:

```text
V2-9 closed PASS at commit 51bcfdb
-> V2-9.7 Operational Memory Factory Activation Program
-> V2-9.8 Active Bounded Memory Growth Campaigns
-> V2-10 12h/24h Lifecycle Readiness Review
-> V2-11 Bounded 12h/24h Lifecycle Proof
-> V2-11.7 extend the operational factory to selective 12h/24h continuation
-> V2-11.8 extended bounded multi-timeframe campaigns
-> V2-12 Memory Corpus Quality Report
-> V2-13 Clean Retrieval Reactivation Review
-> V2-14 WAIT/AVOID/NO_ACTION Paper Decision Readiness
-> V2-15 Paper BUY Readiness Review
```

V2-9.7A through V2-9.7F and V2-9.8A are closed PASS. V2-9.8B remains the active
bounded operational Memory Factory lane. The operational factory active-path
restoration supersedes the candidate-acquisition prerequisite chain. Its
selected implementation checkpoint is `7c38f13816169c69697ed19893b7e12802d9b1b7`;
candidate-foundation adoption first entered the critical path at
`219ad8125a75f52686bfbf5953be0fa4cdca4712`.

The proven two-token discovery/selection/tracking route remains the concurrent
active-slot baseline. Candidate-acquisition N2/N7, global Pump cursor, recovery
and migration-observation admission remain implemented and historically
evidenced but are deferred/experimental, not operational prerequisites.

Current adopted operational envelope (2026-08-26):

`docs/printer-v1-v2-9-8b-four-token-standard-4h-source-stack-adoption.md`

- two cycles;
- exactly two token slots per cycle, ordinals `(1, 2)`;
- up to four concurrent through-4h lifecycle tokens as two overlapping
  two-slot cycles;
- Cycle 2 may overlap Cycle 1 through `WINDOW_15M`, `WINDOW_1H`, and
  `WINDOW_4H`;
- no third cycle; no fifth token; compiled 6-token / 3-cycle max unused;
- standard `WINDOW_15M` → hard-gated `WINDOW_1H` → hard-gated `WINDOW_4H` → stop;
- `WINDOW_12H` / `WINDOW_24H` locked;
- Cycle-2 fresh slots must be campaign-history disjoint;
- adoption creates no authorization and unlocks no campaign.

V2-9.8B remains the active bounded operational Memory Factory lane. The Aug-30
token-local Standard-4H lifecycle-isolation repair implementation is committed
at `27964ebc050bfd263a2db275f092f3ebca7dbe46`. Current repository HEAD before
this stale closeout is `2913c03f4e8cf8246b8ca759721799a92cddf39c`. Stale frozen
HEAD binding remains `abdd210d2d1e0788d241d8a26f09b9a60a105912`.

Final pre-application verdict:

`V2_9_8B_FROZEN_STD4H_PREAPPLICATION_APPROVAL_BLOCKED`

Blocker:

`AUTHORIZATION_EXACT_HEAD_BINDING_DRIFT`

Stale authorization:

`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`

Frozen SHA-256 (byte-identical; do not alter):

`5cd5ca47761458023061e4627999df13fb1ac9b80c80bc836b7e4ba012de290f`

Stale authorization final state:

`STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION`

Exact authoritative DB SHA is
`859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`.
This is a governance/state-binding blocker, not a committed-code defect. DB
binding/health, temporal validity at audit time, runtime zero-state,
authorization SHA/integrity, and Standard-4H envelope passed. No application or
consumption occurred. Do not alter, rebind, renew, delete, rename, move, or
apply the stale package. From this closeout forward, `...b6d7ab46` is
governance-required prior non-reusable for every future Standard-4H package.

Cycle-2 Aug-30 `SELECTED` slot rows remain historical residue under
terminal/drained canonical ownership and must not be mutated. Raw historical
slot state alone must not establish active execution authority.

This stale-authorization closeout and fresh-preparation re-entry become active
only when this six-doc package is committed. Until that commit exists, do not
prepare another authorization. Do not invent the future closeout commit SHA.
The later preparation must bind the actual HEAD produced by that commit.

The exact current next permitted lane after stale-closeout commit is:

```text
FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — STALE PRIOR AUTHORIZATION SEALED NON-REUSABLE
```

Exact currently permitted action:

```text
Prepare exactly one fresh exact-HEAD / exact-DB one-shot Standard-4H authorization package using the existing canonical authorization owners, including V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46 in the complete prior non-reuse trust root, and stop unconsumed for independent package review.
```

That lane is separately approved fresh preparation only. It is NOT an automatic
successor or retry. Application/consumption/execution remain blocked. Preserve:

```text
readiness -> design/specification -> preparation -> independent package review -> explicit application/execution approval -> one-shot bounded execution/proof -> closeout
```

Do not apply, consume, or execute from this guide alone.

Historical at the time of the 2026-08-26 source-stack synchronization:
`POST-SYNCHRONIZATION FRESH NEXT-BOUNDED-CAMPAIGN AUTHORIZATION READINESS /
GOVERNANCE ONLY`. Later retained-evidence, remote-host, migration-062,
authorization-preparation, Aug-30 repair-closeout, post-repair readiness,
authorization-boundary design, and package-review current-state blocks appended
below this section remain historical evidence only and do not override
`CURRENT_HANDOFF.md`, `AGENTS.md`, or this Roadmap Placement for current-lane
selection. Stale authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46` is sealed
non-reusable; post-commit lane is fresh preparation only.

Do not treat this guide, a prior run, or a consumed authorization as current
execution authority. Do not start an operational campaign, invoke providers/RPC,
run N2/N7 or recovery, start V2-10, exceed concurrent capacity two, or unlock
retrieval/paper/financial capabilities from this guide alone.

Do not use this guide to skip V2-9.7, V2-9.8A, corpus-quality reviews, Lane 9
BUY policy, or Lane 10 paper-position policy.

If the active memory-growth build order is updated later, this roadmap placement
must be updated to match the approved order.

## 20. First Recommended Memory Factory Configuration

The first operational Memory Factory configuration is not authorized by this
guide alone. It must come from the committed V2-9.8B operational authority and a
later separate fresh exact-HEAD authorization.

Historical restoration-proof configuration (preserved; superseded for current
envelope authority by the 2026-08-26 adoption):

```text
active_tokens: 2 first
increase_to_3: locked
active_intake: proven two-token operational discovery/selection/tracking
candidate_acquisition_n2_n7: deferred_not_prerequisite
candidate_cursor_recovery_authority: off
WINDOW_5M_MICRO_EVENT: conditional support-only
WINDOW_15M: main closeout for active tokens
WINDOW_1H: locked for the restoration proof
WINDOW_4H: locked for the restoration proof
WINDOW_12H: locked until V2-11.7
WINDOW_24H: locked until V2-11.7
paper_decisions: off
BUY: locked
positions: locked
PnL: locked
retrieval_activation: locked
safe_stop: required
auto_restart_after_terminal_failure: forbidden
```

Current adopted bounded operational envelope (capability only; not an
authorization):

```text
policy_family: V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1
active_cycles: 2
slots_per_cycle: 2
concurrent_through_4h_tokens: 4
distinct_token_identities_across_campaign: up_to_4
third_cycle_or_fifth_token: locked
compiled_6_token_3_cycle_maximum: unused
candidate_acquisition_n2_n7: deferred_not_prerequisite
candidate_cursor_recovery_authority: off
WINDOW_5M_MICRO_EVENT: conditional support-only
WINDOW_15M: root main closeout
WINDOW_1H: hard-gated standard continuation
WINDOW_4H: hard-gated standard continuation; automatic stop boundary
WINDOW_12H: locked
WINDOW_24H: locked
cycle2_fresh_slots: campaign_history_disjoint_required
paper_decisions: off
BUY: locked
positions: locked
PnL: locked
retrieval_activation: locked
safe_stop: required
auto_restart_after_terminal_failure: forbidden
authorization_created_by_this_guide: false
```

Historical V2-9.8A operator-activation instruction — preserved for provenance,
not current execution authority: at the closed V2-9.8A gate, the assistant was
required to provide the exact verified PowerShell command from the committed
implementation. That command had to contain no placeholders, target the
authoritative persistent corpus DB, avoid proof DBs and the V2-9 proof launcher,
run bounded automatic cycles, use Source Governor and Central Scheduler, perform
discovery through reporting and safe shutdown, never automatically restart after
terminal failure, and preserve all retrieval and financial locks.

Current command/launch authority is not created by this guide or by the
2026-08-26 source-stack synchronization. Any live operational command may be
provided only under a later fresh exact-HEAD authorization lane after the
required post-synchronization readiness/governance step, with separate explicit
operator approval. No existing or consumed authorization may be reused.

The first goal is not trading.

The first goal is proving that the Memory Factory can grow clean persistent
memory without polluting the corpus database.

## 21. Required Future Build Pattern

Every future Memory Factory implementation lane must specify:

- exact lane goal
- exact files/tables affected
- exact windows enabled
- exact source budgets
- exact token caps
- exact stop conditions
- exact dirty-memory gates
- exact report output
- exact forbidden behaviors
- targeted tests
- nearby tests
- full suite only at lane close
- manual operator proof
- no commit/tag until proof passes

Every task must end with:

- files changed
- what was built
- what was not touched
- tests/checks run
- pass/fail status
- risks or concerns
- next recommended lane

## 22. Acceptance Checklist

This guide is acceptable only if future work using it preserves all of the following:

- Post-RC Build Order remains active roadmap
- Clean Master Spec remains product/system law
- AGENTS.md remains build discipline law
- V1 remains Solana-only
- V1 remains Solana memecoin-only
- V1 remains paper-only
- no live wallet
- no private keys
- no real funds
- no live execution
- no paid API dependency
- no scoring/ranking/confidence/weighted system
- no Source Governor bypass
- no Central Scheduler bypass
- no dirty-memory decisions
- no 5m main outcome memory
- no 5m-only retrieval unlock
- no 5m-only paper decision unlock
- no BUY unlock from this guide
- no paper position unlock from this guide
- no PnL unlock from this guide
- no fake profit
- no look-ahead bias
- no winner-only dataset
- no runtime expansion without approved lane
- no long-window activation before approved lane
- clear operator reports
- clear stop conditions
- clean-memory yield tracked separately from total rows

## 23. Final Memory Factory Rule

Printer must become smart before it becomes active.

The Memory Factory exists to grow clean, realistic, multi-timeframe memory so future paper decisions are based on what Printer has actually seen.

The goal is not to chase every pump.

The goal is to learn which pumps were tradable, which pumps were traps, which exits were realistic, which exits failed, which waits saved money, which avoids protected capital, and which paper outcomes were honest enough to train future decisions.

In V1, memory comes first.

Paper realism comes second.

Audited decisions come third.

Live trading is never part of V1.

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

<!-- V2_9_8B_POST_MIGRATION_062_READINESS_CURRENT_STATE_START -->
## V2-9.8B Post-Migration 062 Fresh Next-Bounded-Campaign Readiness — Current Authority

This block supersedes older current-looking migration, post-campaign,
remote-host, and next-bounded-campaign readiness pointers for current-lane
selection. Historical text remains evidence only.

- migration application verdict:
  `V2_9_8B_MIGRATION_062_CONTROLLED_APPLICATION_PASS`
- migration-application synchronization commit:
  `52bf15365bbf500ffe61f1b49a4d9ca38d1c3363`
- authoritative DB SHA-256:
  `dececa7ce402856978675c66ecbdfd23b88ed97e3ff23f282a2588a436c93836`
- migration state: `62 / 062_pre_admission_attempt_evidence.sql`
- reviewed product-code repair:
  `91ec3131318f5bff4d3c6dfed12b09c5b6747827`
- consumed authorization
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7`
  remains permanently non-reusable
- readiness verdict:
  `V2_9_8B_POST_MIGRATION_FRESH_NEXT_BOUNDED_CAMPAIGN_READINESS_GOVERNANCE_PASS`
- historical `NO_PAIR / DURATION_EXHAUSTION` classification remains
  `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE`
- no campaign, authorization, provider/RPC/WebSocket, Source Governor, Central
  Scheduler, retrieval, financial, or remote-host action occurred in readiness

Governing closeout:

`docs/printer-v1-v2-9-8b-post-migration-062-fresh-next-bounded-campaign-readiness-governance-closeout.md`

The exact current permitted lane is:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

Any fresh authorization must bind the final committed readiness HEAD and the
exact DB SHA above. Preparation/review does not execute Printer, and later
consumption/execution requires separate explicit operator approval. All
permanent V1 locks remain unchanged.
<!-- V2_9_8B_POST_MIGRATION_062_READINESS_CURRENT_STATE_END -->

<!-- V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_CURRENT_STATE_START -->
## V2-9.8B Migration-062 Authorization-Provenance — Current Authority

This block supersedes older current-looking authorization-preparation and
migration-provenance pointers for current-lane selection. Historical text
remains evidence only.

Fresh authorization preparation is blocked by
`EVIDENCE_CONTROL_BLOCKER__CURRENT_MIGRATION_PROVENANCE_PIN_STILL_061`.
The existing verified migration-062 application package is sufficient and must
not be rerun or replaced. Audit and design are closed:

- `V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_EVIDENCE_CONTROL_AUDIT_PASS`
- `V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_EVIDENCE_CONTROL_DESIGN_PASS`

Governing design:

`docs/printer-v1-v2-9-8b-migration-062-authorization-provenance-evidence-control-design.md`

The exact current permitted lane is:

`MIGRATION-062 AUTHORIZATION-PROVENANCE EVIDENCE-CONTROL IMPLEMENTATION / BOUNDED PROOF ONLY`

That later lane requires explicit operator approval. It may not create, apply,
or consume an authorization; mutate the authoritative DB; run Printer,
providers/RPC/WebSocket, or Central Scheduler; start a campaign; or resume
remote-host work. Migration 061 and consumed authorization
`V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260827T122355Z_8e43eae7` remain permanently
historical/non-reusable. All permanent V1 locks remain unchanged.
<!-- V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_CURRENT_STATE_END -->

<!-- V2_9_8B_MIGRATION_062_PROVENANCE_IMPLEMENTATION_CURRENT_STATE_START -->
## V2-9.8B Migration-062 Provenance Implementation — Current Authority

This block supersedes older current-looking provenance implementation and
authorization-preparation pointers for current-lane selection.

Implementation and independent closeout verdicts:

`V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_EVIDENCE_CONTROL_IMPLEMENTATION_PASS`

`V2_9_8B_MIGRATION_062_AUTHORIZATION_PROVENANCE_EVIDENCE_CONTROL_IMPLEMENTATION_CLOSEOUT_PASS`

Governing closeout:

`docs/printer-v1-v2-9-8b-migration-062-authorization-provenance-evidence-control-implementation-closeout.md`

Both four-token profiles now bind exact migration-062 current provenance;
migration 061 remains immutable historical evidence. At that historical
checkpoint the exact lane was:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT AUTHORIZATION PREPARATION / INDEPENDENT REVIEW`

That pointer is historical after later Aug-30 repair closeout and post-repair
readiness PASS. No authorization application/consumption, database mutation,
Printer/provider/Scheduler/campaign, or remote-host work is authorized by this
historical block. All permanent V1 locks remain unchanged.
<!-- V2_9_8B_MIGRATION_062_PROVENANCE_IMPLEMENTATION_CURRENT_STATE_END -->

<!-- V2_9_8B_POST_REPAIR_READINESS_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Post-Repair Next-Bounded-Campaign Readiness — Historical Authority

This block is historical after the later authorization-boundary design PASS.
Readiness closeout commit remains `7d5c3a631091af7e07f941fe56647d6ffc596d46`.
Historical text remains evidence only.

- readiness verdict:
  `V2_9_8B_POST_REPAIR_NEXT_BOUNDED_CAMPAIGN_READINESS_PASS`
- independent readiness operator review: `PASS`
- readiness closeout / design baseline:
  `7d5c3a631091af7e07f941fe56647d6ffc596d46`
- authoritative DB SHA-256:
  `859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`

At readiness-closeout time, the next permitted lane was authorization-boundary
design / specification. That pointer is historical after design review PASS.
<!-- V2_9_8B_POST_REPAIR_READINESS_CLOSEOUT_CURRENT_STATE_END -->

<!-- V2_9_8B_AUTH_BOUNDARY_DESIGN_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Next Standard-4H Authorization-Preparation Boundary Design — Historical Authority

This block is historical after the later independent package review PASS.
Preparation-bound HEAD remains `abdd210d2d1e0788d241d8a26f09b9a60a105912`.
Historical text remains evidence only.

- design: `NEXT STANDARD-4H AUTHORIZATION-PREPARATION BOUNDARY DESIGN`
- independent design operator review: `PASS`
- implementation-boundary classification: `EXISTING_OWNER_ALREADY_SUFFICIENT`

At design-closeout time, the next permitted lane was authorization preparation.
That pointer is historical after package preparation and independent review PASS.
<!-- V2_9_8B_AUTH_BOUNDARY_DESIGN_CLOSEOUT_CURRENT_STATE_END -->

<!-- V2_9_8B_AUTH_PACKAGE_REVIEW_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Next Standard-4H Authorization Package Review — Historical Authority

This block is historical after the later stale exact-HEAD-drift closeout.
Historical text remains evidence only. The package-review closeout document
remains historically correct for the state when written.

- independent package review: `PASS`
- authorization ID:
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`
- frozen SHA-256:
  `5cd5ca47761458023061e4627999df13fb1ac9b80c80bc836b7e4ba012de290f`
- package state at review time: `PREPARED / UNCONSUMED / UNAPPLIED`
- frozen HEAD: `abdd210d2d1e0788d241d8a26f09b9a60a105912`
- frozen DB SHA-256:
  `859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`

At package-review closeout time, the next permitted lane was application /
execution approval. That pointer is historical after pre-application
`AUTHORIZATION_EXACT_HEAD_BINDING_DRIFT`.
<!-- V2_9_8B_AUTH_PACKAGE_REVIEW_CLOSEOUT_CURRENT_STATE_END -->

<!-- V2_9_8B_STALE_AUTH_HEAD_DRIFT_CLOSEOUT_CURRENT_STATE_START -->
## V2-9.8B Stale Standard-4H Authorization Exact-HEAD-Drift Closeout — Current Authority

This block supersedes older current-looking package-review, design, readiness,
and authorization-preparation pointers in this guide for current-lane
selection. Historical text remains evidence only.

- preapplication verdict:
  `V2_9_8B_FROZEN_STD4H_PREAPPLICATION_APPROVAL_BLOCKED`
- blocker: `AUTHORIZATION_EXACT_HEAD_BINDING_DRIFT`
- classification: governance/state-binding blocker; NOT a committed-code defect
- stale authorization ID:
  `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46`
- frozen SHA-256:
  `5cd5ca47761458023061e4627999df13fb1ac9b80c80bc836b7e4ba012de290f`
- stale final state:
  `STALE / UNCONSUMED / UNAPPLIED / PERMANENTLY INELIGIBLE FOR APPLICATION`
- current HEAD before closeout:
  `2913c03f4e8cf8246b8ca759721799a92cddf39c`
- stale frozen HEAD binding:
  `abdd210d2d1e0788d241d8a26f09b9a60a105912`
- authoritative DB SHA-256:
  `859f3712d19ffdf9e8d87d967649864935098058996d988f607faf9eb7cc6552`
- DB binding/health, temporal validity at audit time, runtime zero-state,
  authorization SHA/integrity, and Standard-4H envelope passed
- no application/consumption occurred; do not describe as consumed
- stale ID is now governance-required prior non-reusable for future packages
- closeout:
  `docs/printer-v1-v2-9-8b-stale-standard-4h-authorization-head-drift-closeout.md`

This stale-authorization closeout and fresh-preparation re-entry become active
only when this six-doc package is committed. Until that commit exists, do not
prepare another authorization.

After closeout commit, the exact current permitted lane is:

`FRESH EXACT-HEAD / EXACT-DB ONE-SHOT STANDARD-4H AUTHORIZATION PREPARATION — STALE PRIOR AUTHORIZATION SEALED NON-REUSABLE`

Exact currently permitted action:

`Prepare exactly one fresh exact-HEAD / exact-DB one-shot Standard-4H authorization package using the existing canonical authorization owners, including V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260831T150842Z_b6d7ab46 in the complete prior non-reuse trust root, and stop unconsumed for independent package review.`

Separately approved fresh preparation only. NOT automatic successor/retry.
Application/consumption/execution remain blocked. Preserve:

```text
readiness -> design/specification -> preparation -> independent package review -> explicit application/execution approval -> one-shot bounded execution/proof -> closeout
```

All permanent V1 locks remain unchanged.
<!-- V2_9_8B_STALE_AUTH_HEAD_DRIFT_CLOSEOUT_CURRENT_STATE_END -->

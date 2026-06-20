**Printer V1 Final Build Order**

*Codex Build Version*

A unified build sequence for turning Printer into one clean Solana memecoin memory and paper-trading machine.

# Purpose of This Document

**This document defines the final build order for Printer V1.** Printer must be built as one machine, not as disconnected engines. The purpose is to avoid unnecessary mistakes, bugs, patch-heavy development, engine conflicts, snapshot starvation, and weak memory caused by different parts of Printer competing with one another.

**Printer V1 should be built lifecycle-first:** discover token -> classify tracking priority -> collect snapshots -> enrich with safety, liquidity, flow, chart, market, and chain context -> close memory windows -> build clean episodes -> compare memory -> make paper decisions -> audit results -> improve future memory.

# Printer as One Entity

**Printer V1 is a memory-backed Solana memecoin paper-trading system with a central scheduler, shared source governor, shared data model, clean-memory pipeline, and audited paper-decision loop.**

The 10 engines are not separate products. They are internal systems inside one machine. Each part must support the same goal: build enough clean, realistic memory for Printer to learn what historically protected capital or made paper money under similar conditions.

# Core Architecture Classification

| **Layer**                         | **Parts Included**                                                     | **Role in Printer**                                                                                                     |
|-----------------------------------|------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
| **Core Law Layer**                | Part 0 - Master Rules                                                  | Defines what Printer is allowed to do, what it is banned from doing, and the global rules every engine must obey.       |
| **Context Layer**                 | Part 1 - Market Regime Engine; Part 2 - Solana Chain Heat Engine       | Records wider market and Solana meme conditions around each token episode. These are memory context, not trade signals. |
| **Intake Layer**                  | Part 3 - Discovery Engine                                              | Finds tokens and decides whether they should be tracked, watched, ignored, or rejected. Discovery is not alpha.         |
| **Protection + Reality Layer**    | Part 4 - Safety/Rug Filter; Part 5 - Liquidity + Exit Engine           | Checks danger, tradability, entry realism, exit realism, and whether chart profit could realistically be captured.      |
| **Behavior Interpretation Layer** | Part 6 - Trading Flow Engine; Part 7 - Chart/Volatility Engine         | Interprets what the token is doing using stored snapshots and shared source data.                                       |
| **Time + Snapshot Control Layer** | Part 8 - High-Frequency Token-Level Snapshot Scheduler                 | Controls snapshot timing, priority, resource budgets, and prevents engines from fighting for data capacity.             |
| **Memory + Decision Layer**       | Part 9 - Episode/Memory Engine; Part 10 - Paper Trading + Audit Engine | Turns completed windows into clean memory, makes memory-backed paper decisions, and audits outcomes honestly.           |

# Non-Negotiable System Rule

**Printer must have one central scheduler and one source governor.** No engine is allowed to independently spam APIs, create its own timing loop, or bypass tracking priority. If there is resource pressure, open paper trades and token-level snapshots always win.

## Why This Rule Matters

- It prevents duplicate API calls and rate-limit pressure.

- It prevents chain heat and broad context checks from starving token-level snapshots.

- It protects memory windows from becoming incomplete or dirty.

- It stops safety, liquidity, flow, and chart engines from creating conflicting versions of the same truth.

- It gives Codex one clear architecture to follow instead of patching random symptoms later.

# Codex Build Discipline

Printer should not be built with one giant prompt. Every Codex task should be a controlled build lane with a tight scope and a clear exit gate.

- One clear goal per prompt.

- Exact files, modules, tables, or migrations to create or modify.

- Exact things Codex must not touch.

- No unrelated refactors.

- No live trading, no wallet logic, no private keys, no paid API dependency, and no scoring system.

- Required tests or verification commands.

- Required pass/fail report before closing the lane.

- Stop after completing the lane instead of moving into the next phase without approval.

# Final Build Order Summary

**Clean sequence:** Law -> Database -> Source Governor -> Scheduler -> Token Lifecycle -> Discovery -> Token Snapshots -> Market Context -> Chain Heat -> Safety -> Liquidity/Exit -> Trading Flow -> Chart/Volatility -> Micro-Events -> Episode Memory -> Memory Similarity -> Paper Decisions -> Paper Monitoring -> Paper Audit -> Reports -> Hardening.

## Phase 0 - Project Law + AGENTS.md

**Goal:** Lock what Printer is and what it is not before any engine is built.

- Create AGENTS.md with global Printer rules.

- Define global constants/enums for actions, lanes, source status, and memory quality.

- Lock V1 bans: no live trading, no wallet connection, no private keys, no real funds, no paid APIs, no scoring system.

- Codex must read these rules before every future build lane.

## Phase 1 - Database Foundation

**Goal:** Create the shared database structure before building logic.

- Base tables for tokens, pairs/pools, source requests, source responses, failures, tracking queue, scheduler jobs, snapshots, engine outputs, memory windows, episodes, decisions, trades, audits, and run logs.

- No isolated engine-owned truth.

- Every later engine writes into the same lifecycle.

## Phase 2 - Source Registry + Source Governor

**Goal:** Create one shared gatekeeper for all external data.

- Register DexScreener, GeckoTerminal, PumpPortal free launch/migration streams, Alternative.me, CoinGecko, DefiLlama, GoPlus where available, Solana RPC/Helius free tier, and Jupiter quote API for paper simulation only.

- Add rate limits, stale-data rules, retries, failure labels, response normalization, and source health checks.

- No engine calls external sources directly.

## Phase 3 - Central Scheduler + Resource Governor

**Goal:** Build the heart of Printer so engines do not fight for space.

- Create priority queue, job locks, duplicate prevention, retry windows, cooldowns, next-check calculation, and starvation protection.

- Highest priority: open paper trades and active exit-risk tokens.

- Lower priority: discovery refresh, market regime, chain heat, and backup checks.

- This phase protects snapshot quality and clean memory.

## Phase 4 - Token Lifecycle + Tracking Queue

**Goal:** Build the state machine that controls each token journey.

- States: discovered, watch only, track normal, track fast, paper monitoring, cooldown, archived, instant reject memory only.

- Promotion/demotion rules, archive rules, reopen rules, watch-only refresh rules, and priority reason logging.

- Discovery feeds this lifecycle instead of directly triggering heavy tracking.

## Phase 5 - Discovery Engine

**Goal:** Find useful tokens without turning discovery into trading.

- Intake from Pump.fun launches, migrations, DexScreener new pairs, boosted tokens, sudden volume, sudden liquidity, revived tokens, stable tokens, dumps, and micro-pumps.

- Output only TRACK_FAST, TRACK_NORMAL, WATCH_ONLY, IGNORE, or INSTANT_REJECT.

- No token moves from Discovery directly to paper BUY.

## Phase 6 - Token-Level Snapshot System

**Goal:** Start collecting the real path of tracked tokens.

- Capture price, liquidity, volume, transactions, FDV/market cap where available, pair age, token age, source status, quote/route status where relevant, tracking lane, and snapshot mode.

- Add snapshot quality labels, missed snapshot detection, window coverage tracking, and snapshot gap audits.

- Build this before safety, liquidity, flow, and chart logic so those engines read shared data instead of fetching separately.

## Phase 7 - Market Regime Engine

**Goal:** Attach broad market context to token memory.

- Track BTC/SOL/ETH context, Fear & Greed, market regime labels, transition labels, and nearest-valid snapshot lookup.

- Market regime is not a trade signal. It is memory context.

- It must not override memory or token-level evidence.

## Phase 8 - Solana Chain Heat Engine

**Goal:** Attach Solana memecoin environment context to token memory.

- Track hot, active, rotating, choppy, cooling, dead, manipulated, and unknown Solana meme conditions.

- Track chain heat transitions, tracked meme liquidity, tracked meme volume, hot pair count, new pair count, and migration activity.

- Chain heat must not consume capacity needed for token-level snapshots.

## Phase 9 - Safety / Rug Filter Engine

**Goal:** Protect Printer from obvious traps and record danger memory.

- Check mint/freeze authority, liquidity removal, holder concentration where available, creator risk, metadata/profile risk, and suspicious source conditions.

- Output safety labels like SAFETY_PASS, SAFETY_WATCH, SAFETY_HIGH_RISK, SAFETY_INSTANT_REJECT, and SAFETY_UNKNOWN.

- Safety is not a buy signal; it is a protection layer.

## Phase 10 - Liquidity + Exit Engine

**Goal:** Decide whether chart movement could realistically become paper profit.

- Check entry realism, exit realism, liquidity state, slippage estimate, price impact estimate, route availability, quote age, and liquidity drain labels.

- A green candle is not money. Only realistic entry plus realistic exit can become clean paper profit.

- This phase is critical to prevent fake profit memory.

## Phase 11 - Trading Flow Engine

**Goal:** Understand buyer, seller, transaction, and volume behavior.

- Build buyer pressure, seller pressure, transaction trend, volume trend, fake demand, late buyer trap, seller exhaustion, and flow quality labels.

- Use stored snapshots first. Do not become another API competitor.

- Flow describes behavior; it does not trigger buy or sell alone.

## Phase 12 - Chart / Volatility Engine

**Goal:** Understand the token price path.

- Build pump, dump, wick, breakout, breakdown, consolidation, revival, volatility, and micro-event chart labels.

- Chart movement must be interpreted alongside liquidity, exit realism, trading flow, safety, market regime, chain heat, and completed outcomes.

- Chart is not a buy signal.

## Phase 13 - Micro-Event Engine

**Goal:** Handle fast 5-minute behavior without confusing it with main memory windows.

- Detect 5m micro-pumps, fast pump-dumps, wick-only moves, late-buy traps, tradable micro-pumps, and untradable micro-pumps.

- Measure micro-exit realism and holding-to-15m result.

- 5m is a support window, not a main outcome window.

## Phase 14 - Episode / Memory Engine

**Goal:** Convert completed tracking windows into usable memory.

- Build 15m, 1h, 4h, 12h, and 24h memory windows.

- Validate snapshot coverage, source quality, timing coverage, safety, liquidity, flow, chart, and exit realism.

- Reject incomplete, stale, broken, or unrealistic episodes as DIRTY_MEMORY / DO_NOT_TRAIN.

## Phase 15 - Memory Retrieval + Similarity Engine

**Goal:** Compare the current setup to past clean memories.

- Create setup fingerprints and filters for market regime, chain heat, safety, liquidity, flow, chart, and micro-event match.

- Return similar clean memories, outcomes, best historical action, and worst historical action.

- No score, confidence score, buy score, or combined scoring system.

## Phase 16 - Paper Decision Engine

**Goal:** Make memory-backed paper decisions only.

- Output only BUY, SELL, HOLD, WAIT, AVOID, or NO_ACTION.

- Use the required decision template with current setup, similar memories, historical actions, reason, invalidation condition, and paper trade status.

- If clean memory is not enough, choose WAIT, AVOID, or NO_ACTION depending on risk.

## Phase 17 - Paper Trade Monitor

**Goal:** Track open paper positions with highest priority.

- Record paper entry, paper exit, open position state, unrealized P/L, realistic exit check, hold condition, sell condition, invalidation trigger, exit missed flag, and round-trip detection.

- Open paper trades must get top scheduler priority because memecoin profit can disappear quickly.

- Paper monitoring protects the realism of the audit layer.

## Phase 18 - Paper Audit Engine

**Goal:** Find out whether Printer decisions actually worked.

- Audit profit, loss, avoided loss, missed upside, unrealistic profit, late entry, early sell, bad hold, correct wait, correct avoid, and wrong avoid.

- Output labels such as PAPER_PROFIT_CLEAN, PAPER_PROFIT_UNREALISTIC, EXIT_MISSED, AVOID_PROTECTED_CAPITAL, WAIT_SAVED_MONEY, HOLD_ROUND_TRIPPED, and SELL_PROTECTED_PROFIT.

- Audit turns Printer from event recorder into a learning machine.

## Phase 19 - Reporting + Operator Review

**Goal:** Inspect whether Printer is becoming smarter.

- Report clean memory count, dirty memory count, missed snapshots, missed exits, source failures, paper decision breakdown, paper P/L realism, best/worst memory types, common avoid reasons, fake profit reasons, and scheduler starvation.

- Do not build a polished dashboard before the machine produces meaningful data.

- Reports should expose truth, not hide weakness.

## Phase 20 - Hardening + Long-Run Paper Validation

**Goal:** Stress test the full system before trusting it.

- Test source failure, stale data, duplicate jobs, competing jobs, missed windows, rate-limit pressure, token snapshot starvation, dirty memory rejection, paper exit realism, no-score enforcement, no-live-trading enforcement, and no-paid-API enforcement.

- Run long enough to prove Printer can collect clean memory, reject dirty memory, avoid bad setups, detect fake profit, make memory-backed paper decisions, and audit itself honestly.

- No live trading discussion until this loop is proven under messy real memecoin conditions.

# Locked Priority Rule

**When resources are tight, Printer must prioritize in this order:**

1.  Open paper trades

2.  Active exit-risk tokens

3.  TRACK_FAST micro-event tokens

4.  TRACK_FAST first 15m tokens

5.  TRACK_NORMAL first 15m tokens

6.  Tokens approaching memory-window close

7.  Safety/liquidity refreshes for tracked tokens

8.  Discovery refresh

9.  Market regime context

10. Solana chain heat context

11. Backup source checks

# Final Principle

**Printer should be built to protect memory quality first.** The system can only become useful as a money machine if it captures enough clean snapshots, rejects dirty data, audits paper decisions honestly, and prevents engines from competing with each other. Every part must complement the same loop: clean observation -> clean memory -> memory-backed paper decision -> honest audit.

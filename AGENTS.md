\# Printer V1 Build Rules



Printer V1 is a Solana-only memecoin memory and paper-trading machine.



Printer V1 is paper-trading only.



Use these documents as the source of truth:

\- docs/printer-v1-clean-master-spec.md

\- docs/printer-v1-final-build-order.md



\## Core Goal



Printer's goal is to become a realistic paper-trading money machine by collecting clean Solana memecoin data, building clean historical memory, comparing current setups against past clean memory, making paper-only decisions, and auditing whether those decisions protected capital or produced realistic paper profit.



Printer must avoid fake profit, dirty memory, forced trades, and rushed implementation.



\## Locked V1 Rules



Do not add:

\- live trading

\- wallet connection

\- private keys

\- real fund movement

\- paid API dependencies

\- scoring systems

\- buy score

\- confidence score

\- safety score

\- liquidity score

\- chart score

\- flow score

\- market score

\- combined score



Printer decisions can only be:

\- BUY

\- SELL

\- HOLD

\- WAIT

\- AVOID

\- NO\_ACTION



All decisions must come from clean historical memory comparison.



If there is not enough clean memory, Printer must choose WAIT, AVOID, or NO\_ACTION depending on risk.



\## Architecture Rules



Printer must work as one machine.



No engine may bypass the central scheduler or source governor.



No engine may create its own independent API loop.



No engine may compete with token-level snapshots.



No engine may write isolated memory outside the shared memory pipeline.



No engine may duplicate source-fetching logic that belongs inside the source governor.



Token-level snapshots and open paper-trade monitoring always take priority over broad context engines.



\## Resource Priority Order



When resources, rate limits, or scheduling capacity are tight, use this priority order:



1\. Open paper-trade monitoring

2\. Exit-risk token snapshots

3\. TRACK\_FAST / micro-event token snapshots

4\. TRACK\_NORMAL token snapshots

5\. Memory-window close snapshots

6\. Safety and liquidity refreshes

7\. Discovery refresh

8\. Market regime context

9\. Solana chain heat context

10\. Backup checks



\## Build Order



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



\## Source Rules



Printer V1 may only use free/public data sources.



Allowed free-first sources:

\- DexScreener

\- GeckoTerminal

\- PumpPortal free launch/migration streams

\- Alternative.me Fear \& Greed

\- CoinGecko free/public/Demo

\- DefiLlama

\- GoPlus where available

\- Solana public RPC

\- Helius free tier

\- Jupiter quote API for paper simulation only



Do not add dependency on:

\- paid Birdeye

\- paid LunarCrush

\- paid X API

\- paid smart-wallet tools

\- paid social sentiment tools

\- paid execution infrastructure



If a feature requires paid data, do not build it in Printer V1.



\## Memory Rules



Printer only learns from completed memory windows.



Main memory windows:

\- 15 minutes

\- 1 hour

\- 4 hours

\- 12 hours

\- 24 hours



Support micro-event window:

\- 5 minutes



The 5-minute window is not a main outcome window. It only explains fast pump/dump behavior inside or before the larger windows.



Dirty, stale, incomplete, delayed, or broken data must not become clean memory.



Use memory quality labels:

\- CLEAN\_MEMORY

\- PARTIAL\_MEMORY

\- DIRTY\_MEMORY

\- DO\_NOT\_TRAIN



DIRTY\_MEMORY and DO\_NOT\_TRAIN must never be used for decisions.



\## Decision Rules



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



\## Paper Trading Rules



Printer V1 is paper trading only.



Paper trades must record:

\- entry time

\- entry price

\- entry liquidity

\- entry source status

\- matched clean memories

\- decision reason

\- invalidation condition

\- exit condition

\- exit time

\- exit price

\- exit liquidity

\- realistic or unrealistic profit result



A paper profit is not clean unless entry and exit were realistic.



If the chart moved but Printer could not realistically enter or exit, the result must be marked as unrealistic or fragile.



\## Build Discipline



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



\## Required Response Format



Every Codex task must end with:



\- Files changed

\- What was built

\- What was not touched

\- Tests/checks run

\- Pass/fail status

\- Risks or concerns

\- Next recommended phase


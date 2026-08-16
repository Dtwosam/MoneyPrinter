# Printer V1 V2-9.8B Persistent Multisource Fresh Acquisition Implementation Closeout

**Date:** 2026-08-16  
**Lane:** V2-9.8B persistent multisource fresh acquisition implementation  
**Approved design baseline:** `c9fb16b8f214e4e527f574e7c7dcbeb5cf351455`  
**Fresh current-contract proof SHA:** `0c013246074dc80479cd046da64e97c08f8f9c2c`  
**Verdict:** `PASS_WITH_CLASSIFIED_TEST_DEBT`

## What was implemented

The approved persistent fresh-acquisition design is implemented without widening Printer V1 authority:

- additive migration `057_pre_lifecycle_discovery_refresh_work.sql` provides dedicated per-refresh persistent work ownership;
- legacy `printer_discovery_work` is not repurposed for the new refresh lifecycle;
- the pre-lifecycle refresh owner supports multiple bounded refresh ordinals under one lawful consumed authorization;
- the bounded acquisition horizon is 2400 seconds with the approved 600-second cadence;
- delayed refresh composition reuses the existing governed Pump-origin, DexScreener, GeckoTerminal, and protocol/liquidity fallback surfaces;
- source ordering rotates categorically by ordinal and does not rank, score, weight, or confidence-rate mints;
- source budgets remain cumulative across rounds and are not reset;
- exact mint/pair deduplication is preserved across rounds;
- capacity and deadline stops remain bounded and fail closed;
- campaign active-work / clean-terminal accounting includes the new refresh-work rows;
- the prior temporal owner import surface remains available as a compatibility facade to the persistent owner.

## Verification evidence

### Current-contract closeout gate

GitHub Actions run `31957087767`, job `95189246628`, on exact SHA `0c013246074dc80479cd046da64e97c08f8f9c2c` completed successfully.

It performed:

- `python -m compileall -q src/printer_v1`;
- current-contract V2-9.8B tests: **51 passed**;
- permanent discovery availability tests with one proven obsolete migration-head assertion deselected: **31 passed, 1 deselected**;
- `git diff --check`.

The current-contract gate therefore completed with **82 passing tests and zero active-contract failures**.

### Focused implementation proof

GitHub Actions sharded closeout run `31956919630`, core job `95188844789`, completed successfully with **19 passed** across:

- persistent multisource refresh behavior;
- persistent refresh-owner proof;
- migration 057 upgrade proof;
- integrated readiness regression.

This proof also ran `compileall` and `git diff --check` successfully.

### Cross-cutting accounting proof

The same sharded closeout run, accounting job `95188844835`, completed successfully with **29 passed** across terminal safety/accounting finalization and multi-round market-batch six-unit sequencing.

## Broad-regression classification

A repository-wide monolithic run was attempted but is not a useful terminal gate for this lane: the repository contains historical tests with real sleeps, slow worker shutdowns, stale migration-head assertions, and other pre-existing failures. A differential attempt reproduced an unrelated lifecycle timeout on both the implementation state and the approved design baseline.

The subsequent sharded audit made the remaining failures attributable:

1. **Proven baseline-stale migration assertions.** The approved design baseline already contains migrations through `056`, while historical tests still assert that `050`, `052`, `054`, or `055` is the current/final schema head. These are not regressions introduced by migration 057.
2. **Superseded temporal-contract tests.** Historical temporal tests still require the former 900-second horizon, reuse legacy `printer_discovery_work` for refresh ownership, omit the now-required persistent `db_path`, or assume the old single-refresh slot behavior. Those expectations conflict directly with the approved V2-9.8B design and cannot be used to force production rollback.
3. **No new production defect was demonstrated by the broad attempts.** The active contract, migration upgrade, persistent owner, multisource composition, integrated readiness, supply, wrapper-lock, and accounting proofs are green.

This debt is recorded rather than silently repaired because widening this implementation lane into historical test-suite maintenance would violate minimum-sufficient risk-based closeout and would not improve the approved production capability.

## Money usefulness

The lane improves Printer's ability to obtain enough fresh, evidence-backed Solana memecoin candidates during a bounded pre-lifecycle acquisition period. It can now persist and resume delayed refresh work across multiple ordinals and multiple existing free/public source paths without resetting budgets, duplicating candidates, bypassing governors, or weakening evidence requirements.

## Functionality risks / setbacks / efficiency blockers

- Historical test debt makes a literal all-repository green suite an inefficient and misleading closeout criterion until those old tests are separately maintained.
- Several old temporal tests should eventually be retired or rewritten against the persistent 057 ownership contract; they are not authority for this lane.
- No live-market four-token proof was run in this implementation lane, by design.
- Provider scarcity, honest source unavailability, and insufficient reachable market evidence remain valid bounded outcomes; this lane does not convert them into code defects.

## Locks preserved

This closeout does **not** authorize or unlock:

- live wallets, private keys, signing, real funds, or live execution;
- paid API dependencies;
- scoring, ranking, confidence percentages, or weighted decision logic;
- embeddings/vectors;
- Source Governor or Central Scheduler bypass;
- dirty-memory retrieval or decision use;
- retrieval or financial capability before its explicit approved lane;
- BUY/SELL/HOLD, paper positions, trade events, paper audits, or PnL before their explicit approved lanes;
- standalone main-outcome authority for `WINDOW_5M_MICRO_EVENT`;
- longer windows before their approved lanes.

## Closeout

V2-9.8B persistent multisource fresh acquisition implementation is **closed** with verdict `PASS_WITH_CLASSIFIED_TEST_DEBT`.

The next action must follow the active Printer V1 source stack and build order. This closeout does not itself authorize a live four-token proof or any downstream financial capability.

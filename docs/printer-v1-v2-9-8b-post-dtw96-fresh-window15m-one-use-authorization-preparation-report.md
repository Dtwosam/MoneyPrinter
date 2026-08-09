# Printer V1 — V2-9.8B Post-DTW96 Fresh WINDOW_15M One-Use Authorization Preparation

## Status

`V2_9_8B_POST_DTW96_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_READY_FOR_LOCAL_REVIEW`

This is preparation only. It does not itself create an authorization, application marker, wrapper invocation, Printer runtime, Scheduler runtime, or WINDOW_15M lifecycle.

## Preparation baseline

- Rereadiness closeout commit: `2cf72d25fea8f71c372a9124974597de2cbd8f78`
- Rereadiness verdict: `V2_9_8B_POST_DTW96_WINDOW_15M_REREADINESS_CLOSEOUT_PASS`
- Implementation commit: `1535bddd05e9d1a5e59c8c1c6fc34be235b991dd`
- Implementation closeout: `e7d19cc8fb6074b3b74740b116d265c3a2f3e8b5`

The final authorization package, if preparation passes, must bind the exact HEAD containing this preparation report. Any later Git change invalidates that binding and requires a new preparation/review.

## Current authoritative database identity

The post-DTW96 read-only rereadiness established:

- Path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `274e3d660e45f1c872e633847f5bf87a2fcdca102ca35e2a8605c1516d9711ae`
- Size: `73138176`
- Inode: `1230526`
- mtime_ns: `1786269650301884824`
- Migration count: `53`
- Migration head: `053_pilot_input_readiness_route_domain.sql`
- Migration-ledger digest: `7431c09f51fd30fefaa6266bbbcd1049e1a8349f12bdb55c468e3b4088208bf1`
- Integrity: `ok`
- Foreign-key violations: `0`
- Sidecars: none

The authorization preparation must re-measure this exact identity before creating any package and must prove the DB remains unchanged throughout preparation.

## Required readiness state

Before authorization creation, the local preparation helper must prove all of the following without source/provider runtime:

- migration ledger guard PASS;
- source contract READY with zero external requests;
- concrete WINDOW_15M composition READY;
- runtime dependency preflight READY;
- holder budget READY;
- all active operational counts zero;
- locked capability baseline valid;
- historical paper-audit baseline preserved;
- authoritative DB identity exactly matches the post-DTW96 rereadiness identity;
- no DB sidecars;
- DB unchanged during preparation;
- no existing application marker for the new authorization ID;
- no wrapper/runtime has started under the new authorization.

## Prior authorization non-reuse

`V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z` is permanently consumed and must never be reused.

The local preparation helper must enumerate the prior authorization history from durable operator artifacts and include every prior authorization in the non-reusable set. It must not trust an assumed count if durable evidence differs.

A new authorization ID must be fresh, unique, and absent from all prior authorization/application-marker history.

## Authorization contract

If and only if all preparation checks pass, the generated package must be:

- `WINDOW_15M` only;
- one-use;
- operator-approved runtime only;
- bound to the exact preparation branch and frozen preparation HEAD;
- bound to the exact authoritative DB identity above;
- temporally bounded for 24 hours;
- fail-closed on Git or DB drift;
- fail-closed if the application marker already exists;
- no retry, rerun, restart, resume, or successor under the same authorization;
- ordinary wrapper application only after an independent authorization review/closeout passes.

The package must not authorize `WINDOW_1H+`, selective 1h continuation, retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper trade audits, or PnL.

## Runtime locks retained

- Solana-only and Solana memecoin-only.
- Paper-only; no wallet/private keys/real funds/live execution.
- Source Governor remains mandatory.
- Central Scheduler remains mandatory.
- Stage reservations remain `3/2/6/7/8/4`.
- `MINIMUM_FREEZE_DEPTH=4` remains locked.
- Active selection capacity remains `2`.
- No migration-registry membership confirmation may be reintroduced for discovered/selected candidates.
- PumpSwap protocol/account validation remains required.
- `WINDOW_5M_MICRO_EVENT` remains support-only.
- `WINDOW_1H+` remains locked.
- No retrieval or financial/paper-trading capability is unlocked.

Any actual WINDOW_15M wrapper invocation must run with `caffeinate -dimsu` so host sleep cannot recreate the DTW93 lease failure.

## Money-usefulness contribution

A fresh authorization bound to the repaired code and current clean DB state allows one more bounded operational WINDOW_15M proof of the memory-production path while preserving the evidence and safety controls needed for useful clean memory.

## What this preparation improves

- freezes exact post-DTW96 Git provenance;
- freezes the new post-DTW96 authoritative DB identity;
- makes prior authorization non-reuse explicit;
- defines the exact checks required before a new one-use package may exist.

## What this preparation still does not unlock

It does not create an authorization by itself and does not authorize runtime. It does not unlock WINDOW_1H+, retrieval, decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL.

## Proof required before completion

A local zero-source/zero-runtime preparation helper must emit a PASS package review containing:

- exact branch and frozen preparation HEAD;
- exact DB fingerprint and unchanged-before/after proof;
- migration/source/composition/dependency/budget readiness;
- zero active residue;
- complete prior non-reusable authorization history;
- fresh authorization ID/path/SHA;
- 24-hour validity;
- marker absent;
- wrapper/runtime not invoked.

After that package exists, an independent GitHub/docs closeout must review it before any wrapper invocation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Any Git drift after the frozen preparation HEAD invalidates authorization binding.
- Any authoritative DB mutation or sidecar appearance invalidates the rereadiness fingerprint.
- Reusing a consumed authorization would violate one-use safety.
- Raising source/stage budgets, lowering freeze depth, weakening tracking rules, or widening lease/heartbeat behavior is outside this preparation and forbidden.
- A preparation PASS is not operational proof; the later wrapper run may still truthfully BLOCK on bounded market/evidence conditions.

## Stop condition

Freeze this preparation report, then run only the local zero-source/zero-runtime authorization preparation helper. After it creates a fresh package, stop for independent authorization review/closeout before any runtime invocation.

# Printer V1 — V2-9.8B Post-DTW97 Fresh WINDOW_15M One-Use Authorization Preparation

## Status

`V2_9_8B_POST_DTW97_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_READY_FOR_LOCAL_REVIEW`

This is preparation only. It does not itself create an authorization, application marker, wrapper invocation, Printer runtime, Scheduler runtime, or WINDOW_15M lifecycle.

## Preparation baseline

- Rereadiness closeout commit: `56f4906a4a89426da4491e5153ba19f6fc1b4c21`
- Rereadiness verdict: `V2_9_8B_POST_DTW97_WINDOW_15M_REREADINESS_CLOSEOUT_PASS`
- Consumed DTW97 authorization: `V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z`
- Consumed DTW97 application-marker SHA-256: `825e2bd7c03b4334580de18153af7869ba92244548eca9de12c3e0567e1921d0`

The final authorization package, if local preparation passes, must bind the exact HEAD containing this preparation report. Any later Git change invalidates that binding and requires a new preparation/review.

## Current authoritative database identity

The post-DTW97 rereadiness established:

- Path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `05633f85b2ca7849998217686ad2b0a5682d304503391186ee0d911a0c13fd15`
- Size: `74018816`
- Inode: `1230526`
- mtime_ns: `1786278235292597742`
- Migration count: `53`
- Migration head: `053_pilot_input_readiness_route_domain.sql`
- Migration-ledger digest: `7431c09f51fd30fefaa6266bbbcd1049e1a8349f12bdb55c468e3b4088208bf1`
- Integrity: `ok`
- Foreign-key violations: `0`
- Sidecars: none

The local preparation must re-measure this exact identity before creating any package and prove the DB remains unchanged throughout preparation.

## Required readiness state

Before authorization creation, the local preparation must prove without source/provider runtime:

- migration-ledger guard PASS;
- source contract READY with zero external requests;
- concrete WINDOW_15M composition READY;
- runtime dependency preflight READY;
- holder budget READY;
- all active operational/Scheduler counts zero;
- locked capability baseline valid;
- historical null-position paper-audit baseline preserved at exactly one;
- authoritative DB identity exactly matches the rereadiness identity;
- no DB sidecars;
- DB unchanged during preparation;
- no existing application marker for the fresh authorization ID;
- no wrapper/runtime started under the fresh authorization.

## Prior authorization non-reuse

`V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z` is permanently consumed and must never be reused.

The local preparation must reconcile durable prior authorization identities and include DTW97 in the permanent non-reusable set. Historical non-reuse is an identity trust root, not a requirement that every older package directory still exist.

A new authorization ID must be fresh, unique, and absent from prior authorization/application-marker history.

## Authorization contract

If and only if all preparation checks pass, the generated package must be:

- `WINDOW_15M` only;
- one-use;
- operator-approved runtime only;
- bound to the exact preparation branch and frozen preparation HEAD;
- bound to the exact authoritative DB identity above;
- temporally bounded for 24 hours;
- fail-closed on Git or DB drift;
- fail-closed if its application marker already exists;
- no retry, rerun, restart, resume, or successor under the same authorization;
- usable only after an independent authorization review/closeout passes.

The package must not authorize WINDOW_1H/4H/12H/24H, selective 1h continuation, retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper trade audits, or PnL.

## Runtime locks retained

- Solana-only and Solana memecoin-only.
- Paper-only; no wallet/private keys/real funds/live execution.
- Source Governor remains mandatory.
- Central Scheduler remains mandatory.
- No scoring/ranking/confidence/weighted decision system.
- No paid API dependency.
- No embeddings/vectors unless later explicitly approved.
- No migration-registry membership confirmation for market-present nominees; direct Pump migration discovery may itself originate from the migration registry.
- PumpSwap protocol/account validation remains required.
- `WINDOW_5M_MICRO_EVENT` remains support-only.
- WINDOW_1H/4H/12H/24H remain locked.
- No retrieval or financial/paper-trading capability is unlocked.

Any later actual WINDOW_15M wrapper invocation must run with `caffeinate -dimsu`, and the terminal must remain untouched until the wrapper visibly returns or terminates.

## Money-usefulness contribution

A fresh authorization bound to the current clean Git and DB state permits the next bounded operational WINDOW_15M proof of the memory-production path without weakening the source, Scheduler, evidence, memory, or financial safety rules required for useful clean memory.

## What this preparation improves

- freezes post-DTW97 Git provenance for a successor authorization;
- freezes the exact current authoritative DB identity;
- makes DTW97 non-reuse explicit;
- defines the minimum checks required before a new one-use package may exist.

## What this preparation still does not unlock

It does not create an authorization by itself and does not authorize runtime. It does not unlock WINDOW_1H+, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL.

## Proof required before completion

A local zero-source/zero-runtime authorization preparation must emit a PASS result containing:

- exact branch and frozen preparation HEAD;
- exact DB fingerprint and unchanged-before/after proof;
- migration/source/composition/dependency/budget readiness;
- zero active residue;
- prior non-reusable authorization reconciliation including DTW97;
- fresh authorization ID/path/SHA;
- 24-hour validity;
- marker absent;
- wrapper/runtime not invoked.

After the package exists, it requires an independent authorization review/closeout before any wrapper invocation.

## Functionality Risks / Setbacks / Efficiency Blockers

- Any Git drift after the frozen preparation HEAD invalidates authorization binding.
- Any authoritative DB mutation or sidecar appearance invalidates the rereadiness fingerprint.
- Reusing DTW97 or any consumed authorization violates one-use safety.
- Historical package-directory retention must not be confused with permanent authorization-ID non-reuse.
- Raising source/stage budgets, weakening tracking/source/Scheduler rules, or widening capability scope is outside this preparation.
- A preparation PASS is not operational proof; a later authorized WINDOW_15M run may still truthfully BLOCK on bounded market/evidence conditions.
- WINDOW_1H+ remains locked.

## Stop condition

Freeze this preparation report, then perform only the local zero-source/zero-runtime authorization preparation. After it creates a fresh package, stop for independent authorization review/closeout before any runtime invocation.

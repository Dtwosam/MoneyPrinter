# Printer V1 V2-9.8B — Post-DTW82 Fresh WINDOW_15M One-Use Authorization Report

Date: 2026-08-08

Linear: `DTW-83`

## Verdict

`V2_9_8B_POST_DTW82_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REPORT_PASS`

The operator explicitly authorized exactly one new real operational ordinary `WINDOW_15M` cycle after DTW-82, with no retry, rerun, resume, restart, or successor.

## Qualified baseline

The corrected Mac alignment/application-readiness gate passed before package creation:

- DTW-82 closeout baseline: `7d44f784eafe8081e024e73a83b386b65c58f61f`;
- authoritative DB SHA-256: `3a27598da678c20b96685722c664e14bca45a950e416c586ffdd1f74258109cf`;
- DB size `69705728`, inode `1230526`, mtime_ns `1786198066668444539`;
- migration count `52`, head `052_memory_observation_eligibility_layers.sql`;
- SQLite sidecars absent;
- integrity `ok`, foreign-key violations `0`;
- no unexpected nonterminal operational state;
- migration-ledger guard PASS;
- approved HTTPS source configuration PASS;
- zero-I/O concrete ordinary `WINDOW_15M` composition PASS;
- no source fetching, Printer/Scheduler runtime, DB mutation, manifest, marker, or new authorization package occurred during readiness.

The historical authority/application inventory was reconciled to 20 known non-reusable authorization IDs. Four previously omitted local application directories were proven historical terminal applications; preserved historical sibling `.staging` residue is inert under the current UUID-scoped wrapper staging semantics and was not deleted or edited.

The currently consumed authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z` remains permanently non-reusable and has no matching current staging residue.

## Authorization boundary

Exactly one fresh authorization package may now be created on this dedicated authorization-preparation branch. The exact commit containing this report is the required `authorized_git.head`.

The package must:

- use schema `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2`;
- use one new unique authorization ID;
- bind `authorized_git.branch` to `agent/v2-9-8b-post-dtw82-window15m-authorization-preparation`;
- bind `authorized_git.head` to the exact commit containing this report;
- bind the authoritative DB with exactly seven keys: `path`, `sha256`, `size`, `inode`, `mtime_ns`, `migration_count`, `migration_head`;
- list all 20 reconciled historical authorization IDs in `prior_authorizations_non_reusable`, lexicographically sorted;
- authorize exactly one manually started ordinary `WINDOW_15M` invocation;
- set automatic retry, manual rerun, resume, restart, successor, scheduled start, and concurrent/second execution to forbidden under the existing package/wrapper contract;
- preserve `WINDOW_5M_MICRO_EVENT` as support-only and keep `WINDOW_1H+` locked;
- preserve Source Governor and Central Scheduler ownership;
- preserve all retrieval, decision, BUY/SELL/HOLD, position, trade, audit, PnL, wallet, key, real-fund, paid-API, scoring/ranking/confidence, embedding, and vector locks.

## Historical non-reusable authorization IDs

1. `V2_9_8B_WINDOW_15M_AUTH_20260801T205700Z`
2. `V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z`
3. `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`
4. `V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z`
5. `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z`
6. `V2_9_8B_WINDOW_15M_AUTH_20260803T232743Z`
7. `V2_9_8B_WINDOW_15M_AUTH_20260804T005013Z`
8. `V2_9_8B_WINDOW_15M_AUTH_20260804T014558Z`
9. `V2_9_8B_WINDOW_15M_AUTH_20260804T141128Z`
10. `V2_9_8B_WINDOW_15M_AUTH_20260804T160827Z`
11. `V2_9_8B_WINDOW_15M_AUTH_20260804T164530Z`
12. `V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z`
13. `V2_9_8B_WINDOW_15M_AUTH_20260805T101248Z`
14. `V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z`
15. `V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z`
16. `V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z`
17. `V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z`
18. `V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z`
19. `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z`
20. `V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z`

## Required review after package creation

Before any manual wrapper invocation, the single package must pass:

1. exact structural/schema review;
2. exact seven-key DB-binding review;
3. package SHA-256 review;
4. exact branch/HEAD binding review;
5. temporal validity review;
6. 20-ID historical non-reuse review;
7. repaired pre-marker Git-provenance/application-boundary review;
8. final non-mutation check confirming no marker or runtime has started.

## What this still does not unlock

This report does not itself create an application marker or start the wrapper/runtime. It does not unlock `WINDOW_1H+`, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, live execution, wallets, private keys, paid APIs, scoring/ranking/confidence systems, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Any tracked change after this report commit invalidates the authorized Git binding.
- Any authoritative DB identity change invalidates the package binding.
- The package is one-use and must not be regenerated, repaired in place, extended, or replaced under this approval if consumed or expired.
- The DTW-81 repair has focused zero-runtime proof and is still awaiting this one bounded real operational exercise.

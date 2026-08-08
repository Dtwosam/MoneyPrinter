# Printer V1 V2-9.8B Post-Repair Fresh WINDOW_15M One-Use Authorization Report

Date: 2026-08-08

Linear: `DTW-77`

## Verdict

`V2_9_8B_POST_REPAIR_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REPORT_PASS`

The operator explicitly authorized exactly one new real ordinary `WINDOW_15M` cycle under DTW-77, with no retry, rerun, resume, restart, or successor.

The required Mac alignment/readiness gate passed against repair baseline `2c19de9758f01aa8642642f0ed70654e4182bdfe` before package creation:

- local branch aligned to `agent/v2-9-8b-post-c8-authorization-exact-binding-repair-implementation`;
- exact HEAD `2c19de9758f01aa8642642f0ed70654e4182bdfe`;
- tracked/index clean;
- authoritative DB SHA-256 `7380f9b4c172c218e6c9ab1fed996a06fcdeb90ff67f2b414d805f280403d54e`;
- DB size `69328896`, inode `1230526`, mtime_ns `1786022001929258221`;
- migration count `52`, head `052_memory_observation_eligibility_layers.sql`;
- no SQLite sidecars;
- integrity `ok`, foreign-key violations `0`;
- no unexpected nonterminal operational state;
- repaired pre-authorization migration-ledger guard PASS;
- zero-I/O concrete composition PASS;
- historical invalid authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z` preserved, with no application marker;
- no new authorization package, manifest, marker, or runtime existed during the readiness gate.

## Authorization boundary

Exactly one fresh package may now be created with a new authorization ID and must bind this report commit as `authorized_git.head`.

Its `authoritative_database` object must contain exactly these seven fields and no others:

1. `path`
2. `sha256`
3. `size`
4. `inode`
5. `mtime_ns`
6. `migration_count`
7. `migration_head`

The repaired guard and later Git-provenance pre-marker validator both remain fail-closed.

The package must preserve:

- Solana-only / Solana-memecoin-only;
- paper-only;
- ordinary `WINDOW_15M` only;
- `WINDOW_5M_MICRO_EVENT` support-only;
- `WINDOW_1H/4H/12H/24H` locked;
- Source Governor and Central Scheduler ownership;
- no paid API dependency;
- no retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- no wallet, private key, signing, real funds, or live execution;
- no scoring/ranking/confidence/weighting/embeddings/vectors;
- exactly one manually started invocation;
- no retry, rerun, resume, restart, successor, second, concurrent, automatic, or scheduled execution.

The historical invalid authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z` is evidence only and must be listed non-reusable. It must not be edited, repaired in place, or reused.

## What this still does not unlock

This report does not itself start the wrapper or runtime. After package creation, the package still requires independent structural, temporal, Git-head, DB-binding, historical-non-reuse, and pre-marker application-boundary review before the single wrapper invocation may be given to the operator.

## Functionality Risks / Setbacks / Efficiency Blockers

- Any tracked code change after this report commit invalidates the exact authorized Git binding.
- Any authoritative DB identity change invalidates the package binding.
- A package with missing or extra DB-binding keys must fail review.
- If the package expires before application, it must not be extended or regenerated under this authority.
- No second package may be created under this DTW-77 approval.

# Printer V1 V2-9.8B — Post-DTW93 Fresh WINDOW_15M One-Use Authorization Preparation

Date: 2026-08-09

## Verdict

`V2_9_8B_POST_DTW93_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_READY`

This is authorization preparation only. No authorization package is created by this document and no runtime is permitted.

## Controlling lineage

- DTW93 rereadiness closeout: `e65b5476de12a1319fd8a66ec160d497088f33ca`
- frozen authorization-preparation branch: `agent/v2-9-8b-post-dtw93-window15m-authorization-preparation`
- active main window: `WINDOW_15M` only
- active token capacity: 2
- `WINDOW_5M_MICRO_EVENT`: support-only
- selective `WINDOW_1H`: false

## Current authoritative DB binding

Any fresh package must bind exactly:

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `6a0f7afc2f4d542854bcf7f1db6857c6405f50f9085dded922fc419e938bfc35`
- size: `71127040`
- inode: `1230526`
- mtime_ns: `1786227161080487776`
- migration count: `53`
- migration head: `053_pilot_input_readiness_route_domain.sql`

The rereadiness guard passed with integrity `ok`, zero FK violations, no SQLite sidecars, exact canonical migration digest, zero DB writes, zero source calls and zero Scheduler runtime calls.

## Historical authorization non-reuse

There are now 22 known historical one-use authorization IDs. All are permanently non-reusable, including consumed DTW93 authorization `V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z`.

A fresh package must contain a new unique authorization ID and preserve the full historical non-reuse set.

## Correct preparation ordering

The preparation must use the corrected two-stage provenance order:

1. exact branch/HEAD and clean tracked state;
2. canonical migration-ledger guard before package creation;
3. non-Git read-only readiness checks only;
4. exact current DB binding recheck;
5. create one fresh untracked authorization package;
6. review the package against the migration guard;
7. build authorization-bound Git-provenance manifest;
8. validate pre-marker provenance with the exact allowed untracked set;
9. prove application marker absent;
10. prove DB unchanged during preparation;
11. stop before wrapper invocation.

Do not run ordinary manifest-less production preflight before package creation. Retained operator artifacts are legitimate and must not be deleted merely to satisfy that gate.

## Host-awake runtime prerequisite

If a later independent authorization closeout permits one real wrapper invocation, it must run under `caffeinate -dimsu` or the exact repository-approved equivalent. This preparation does not invoke it.

## Locks preserved

No retry/rerun/resume/restart/successor; no `WINDOW_1H+`; no retrieval; no paper decisions; no BUY/SELL/HOLD; no positions/trades/audits/PnL; no wallet/private key/real funds/live execution; no paid APIs; no scoring/ranking/confidence/weighted logic; no embeddings/vectors.

## Acceptance gate

Preparation is ready only for a local package-generation/review helper bound to the exact committed preparation HEAD and exact DB identity above. The helper must return PASS and stop at `INDEPENDENT_AUTHORIZATION_CLOSEOUT_BEFORE_WRAPPER_INVOCATION`.

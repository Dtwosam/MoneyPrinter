# Printer V1 — V2-9.8B Post-DTW98 Post-054 Fresh WINDOW_15M One-Use Authorization Independent Review Plan

## Status

`V2_9_8B_POST_DTW98_POST054_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PLANNED`

This review is read-only with respect to the authoritative database and operational runtime. It does not invoke the wrapper, create an application marker, call live sources, start Scheduler runtime, or start WINDOW_15M.

## Frozen preparation baseline

- branch: `agent/v2-9-8b-post-dtw98-post054-window15m-authorization-preparation`
- preparation HEAD before this review-plan commit: `f72020dd2704d9b5691d39d21a2898ccf9743cce`
- preparation verdict: `V2_9_8B_POST_DTW98_POST054_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_READY_FOR_LOCAL_REVIEW`
- rereadiness closeout: `59f78e0519dbff72065b81a2275e0be00bae39be`

The authorization itself remains bound to `f72020dd2704d9b5691d39d21a2898ccf9743cce`; this review-plan commit must not replace or mutate that binding.

## Candidate authorization reported by local preparation

- ID: `V2_9_8B_WINDOW_15M_AUTH_20260809T163540Z`
- expected canonical path: `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T163540Z/final_authorization.json`
- expected SHA-256: `52a036cec8d104cc0bd22ff52a66be33b040515fe518ce06f97d3fb2bd8aed15`
- authorized: `2026-08-09T16:35:40Z`
- expires: `2026-08-10T16:35:40Z`
- allowed invocation count: `1`
- application marker expected absent

## Bound authoritative database

- SHA-256: `a56439948196c68267f6923b4469b33e9a5d8cd2f7e789c3e21b5253c0013dff`
- size: `74747904`
- inode: `1230526`
- mtime_ns: `1786292067595224838`
- migration count: `54`
- migration head: `054_pre_lifecycle_discovery_refresh_wait.sql`
- migration-ledger digest: `b2e26dd36cee8a8fff4839632bb95e02842ed970f6c0ff96ccf08620386ffd2d`

## Independent review requirements

The review must independently prove:

1. authorization file exists at the canonical path and hashes to the expected SHA;
2. package schema/key shape matches the established immediately preceding authorization contract rather than an invented format;
3. authorization ID, time window, one-use count, WINDOW_15M-only scope, exact Git binding, exact DB binding, migration binding, locked higher windows/capabilities, and no-retry/restart/resume/successor rules are exact;
4. retained migration-package-reference fields that still point to the canonical MIG050 package are internally consistent with wrapper resolution and are not misrepresented as the latest applied migration;
5. authorization remains temporally valid and no application marker exists;
6. historical consumed authorization non-reuse set includes DTW98 and excludes the new unconsumed ID;
7. migration guard PASS at 54/54;
8. source contract READY with zero external requests;
9. concrete WINDOW_15M composition READY;
10. runtime dependency preflight READY;
11. holder budget READY;
12. active operational/Scheduler/factory/proof counts all zero;
13. temporal wait table has zero rows and zero WAITING/CLAIMED rows;
14. locked capability baseline remains PASS and historical null-position paper-audit row count remains exactly one;
15. authoritative DB is byte-identical before/after review with no sidecars;
16. no source calls, Scheduler runtime, DB writes, wrapper invocation, Printer runtime, marker creation, or WINDOW_15M execution occurs during review.

## Decision rule

Only an independent review PASS may permit a later single host-awake ordinary WINDOW_15M wrapper invocation. Any mismatch blocks execution. A review PASS is not a WINDOW_15M operational PASS.

## Locks retained

All V1 locks remain unchanged. WINDOW_1H/4H/12H/24H, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, and PnL remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only.

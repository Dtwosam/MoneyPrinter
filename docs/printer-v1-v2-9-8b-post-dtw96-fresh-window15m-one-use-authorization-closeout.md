# Printer V1 V2-9.8B Post-DTW96 Fresh WINDOW_15M One-Use Authorization Closeout

## Verdict

`V2_9_8B_POST_DTW96_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS_RUNTIME_INVOCATION_ALLOWED`

This closeout reviews the fresh one-use authorization package only. It does not claim a WINDOW_15M runtime pass.

## Frozen preparation state

- branch: `agent/v2-9-8b-post-dtw96-window15m-authorization-preparation`
- HEAD: `a64d109b043ba86d73b82276fb34ba28561de093`
- post-DTW96 rereadiness: PASS
- active memory-growth build order remains `docs/printer-v1-memory-growth-build-order-v2.md` inside the active Printer V1 source stack

## Fresh authorization

- id: `V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z`
- file: `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z/final_authorization.json`
- SHA-256: `d64f2b4285aeebf93a4369350da960a9398f38a4123a160ce8e53cb505c66de1`
- authorized at: `2026-08-09T12:01:00Z`
- expires at: `2026-08-10T12:01:00Z`
- temporal status at independent review: `TEMPORALLY_VALID`
- allowed invocation count: 1
- prior non-reusable authorizations: 25 exact IDs

The predecessor `V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z` remains permanently non-reusable. Missing retained directories for older authorization packages do not create reuse authority; the explicit 25-ID non-reuse trust root controls.

## Authoritative database binding

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `274e3d660e45f1c872e633847f5bf87a2fcdca102ca35e2a8605c1516d9711ae`
- size: `73138176`
- inode: `1230526`
- mtime_ns: `1786269650301884824`
- migration count: 53
- migration head: `053_pilot_input_readiness_route_domain.sql`

Independent review proved the database unchanged during review.

## Independent review evidence

- exact historical non-reuse set: PASS, 25 IDs
- authorization SHA and schema: PASS
- exact Git branch/HEAD binding: PASS
- migration/package DB binding: PASS
- source contract: READY, zero external requests
- concrete composition: READY
- dependency preflight: READY
- holder budget: READY
- all active operational counts: zero
- historical paper-audit baseline: one row preserved
- application marker: absent
- wrapper invoked: false
- Printer runtime started: false
- Scheduler runtime started: false
- WINDOW_15M started: false
- pre-marker allowed file count: 25
- pre-marker allowed-file-set SHA-256: `21204a6df8ded425f35c36726552578387ce9d898ae9f8d9521b16672489da1c`

## Runtime guardrails

Exactly one ordinary `WINDOW_15M` wrapper invocation is permitted under this authorization, subject to launch-time guards.

Required:

- runtime Git identity must remain the frozen preparation branch/HEAD above
- use macOS host-awake guard `caffeinate -dimsu`
- no automatic retry, manual rerun, restart, resume, or successor under this authorization
- once the wrapper invokes the child path, the authorization is permanently consumed regardless of outcome
- do not widen lease/heartbeat timing
- preserve Source Governor and Central Scheduler ownership
- preserve PumpSwap protocol/account validation
- do not reintroduce Pump migration-registry confirmation for market-present candidates
- keep the permanent reserve depth at 4, active selection capacity at 2, and discovery stage reservations `3/2/6/7/8/4`

## Money-usefulness contribution

This bounded attempt tests whether the repaired permanent discovery path can spend its existing evidence budget truthfully, maintain the four-deep reserve contract, and progress through ordinary two-token 15-minute observation without the DTW96 pre-I/O reconciliation-budget defect or readiness/reporting contradictions.

## What this lane improves

- independently reviewed one-use provenance for the repaired DTW96 path
- exact DB and Git binding
- preserved non-reuse history
- bounded operational proof permission for ordinary WINDOW_15M only

## What this lane still does not unlock

It does not unlock WINDOW_1H/4H/12H/24H, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, trade audits, PnL, live wallets, private keys, real funds, paid APIs, or embeddings/vectors. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Required post-invocation proof

Judge the attempt by durable terminal truth, not child exit code alone. Verify at minimum:

- exact one-use consumption
- two-token ordinary WINDOW_15M scope
- permanent four-deep reserve and active two-slot selection truth
- reconciliation calls never exceed offered stage capacity
- stage reservations/operation ceilings remain intact
- exhaustion certificate and shortage classification truth if blocked
- lifecycle/window terminal states and memory quality truth
- six-unit accounting consistency
- Scheduler/discovery ownership and cleanup
- DB integrity and zero active/orphan residue after terminalization
- zero forbidden retrieval/decision/position/trade/audit/PnL deltas
- no lease-expiry or cancellation-probe SQLite contention recurrence

## Functionality Risks / Setbacks / Efficiency Blockers

- A different runtime blocker can still appear after the focused repair proof.
- Process exit 0 is not an operational PASS by itself.
- Any terminal failure consumes this authorization and requires consumed-attempt closeout/root-cause work before another authorization.
- No budget, floor, tracking, source, or safety rule may be relaxed merely to force a pass.

## Closeout decision

The authorization is fresh, exact-one-use, temporally valid at review time, provenance-bound, DB-bound, and unconsumed. One host-awake ordinary WINDOW_15M wrapper invocation is now permitted on the frozen preparation branch/HEAD.
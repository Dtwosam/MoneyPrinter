# Printer V1 V2-9.8B Post-DTW97 Fresh WINDOW_15M One-Use Authorization Closeout

## Verdict

`V2_9_8B_POST_DTW97_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_REVIEW_PASS_RUNTIME_INVOCATION_ALLOWED`

This closeout reviews the fresh one-use authorization package only. It does not claim a WINDOW_15M runtime pass.

## Frozen preparation state

- branch: `agent/v2-9-8b-post-dtw97-window15m-authorization-preparation`
- HEAD: `fb789fac9126c1428b544d8eeab9587ebd402082`
- post-DTW97 rereadiness closeout: `56f4906a4a89426da4491e5153ba19f6fc1b4c21`
- rereadiness verdict: `V2_9_8B_POST_DTW97_WINDOW_15M_REREADINESS_CLOSEOUT_PASS`
- active memory-growth build order remains `docs/printer-v1-memory-growth-build-order-v2.md` inside the active Printer V1 source stack

GitHub independently confirmed the preparation branch remained identical to the frozen preparation HEAD before this closeout.

## Fresh authorization

- id: `V2_9_8B_WINDOW_15M_AUTH_20260809T130306Z`
- file: `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T130306Z/final_authorization.json`
- SHA-256: `e37405cd6b0e1cb5295961546baf71d74e99c90b76640ed0eae4679f38ec2a24`
- authorized at: `2026-08-09T13:03:06Z`
- expires at: `2026-08-10T13:03:06Z`
- temporal status at independent review: `TEMPORALLY_VALID`
- allowed invocation count: `1`
- prior permanently non-reusable authorizations: `26`
- application marker present at review: `false`

DTW97 predecessor authorization `V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z` remains permanently non-reusable. Historical authorization IDs remain non-reusable even if an older package directory is no longer retained.

## Authoritative database binding

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- SHA-256: `05633f85b2ca7849998217686ad2b0a5682d304503391186ee0d911a0c13fd15`
- size: `74018816`
- inode: `1230526`
- mtime_ns: `1786278235292597742`
- migration count: `53`
- migration head: `053_pilot_input_readiness_route_domain.sql`

Independent review proved the database remained unchanged during review.

## Independent review evidence

Verdict:

`V2_9_8B_POST_DTW97_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_INDEPENDENT_REVIEW_PASS`

Evidence established:

- exact historical non-reuse set: PASS, 26 IDs
- authorization SHA and schema: PASS
- exact Git branch/HEAD binding: PASS
- migration/package DB binding: PASS
- migration guard: `V2_9_8B_PRE_AUTHORIZATION_MIGRATION_LEDGER_GUARD_PASS`
- source contract: `READY`, external requests `0`
- concrete WINDOW_15M composition: `READY`
- runtime dependency preflight: `READY`
- holder operational budget: `READY`
- all active operational/Scheduler counts: `0`
- historical null-position paper-audit baseline: exactly `1`
- database unchanged during review: `true`
- pre-marker allowed file count: `26`
- pre-marker allowed-file-set SHA-256: `2829d3a87190e5ae7f0e0890699ceb795b29c450278e64d2fcf9e489a2bf0b9d`
- application marker present: `false`
- review source calls: `0`
- review Scheduler runtime calls: `0`
- review database writes: `0`
- wrapper invoked: `false`
- Printer runtime started: `false`
- Scheduler runtime started: `false`
- WINDOW_15M started: `false`

The earlier local zsh extraction/exit-status issues were review-tool invocation issues only. They did not invoke the wrapper, create the application marker, start Printer/Scheduler runtime, call sources, or mutate the authoritative DB.

## Runtime guardrails

Exactly one ordinary `WINDOW_15M` wrapper invocation is now permitted under this authorization, subject to launch-time fail-closed guards.

Required:

- runtime Git identity must remain `agent/v2-9-8b-post-dtw97-window15m-authorization-preparation` at `fb789fac9126c1428b544d8eeab9587ebd402082`
- authoritative DB identity must remain exactly the bound identity above at launch
- authorization must remain temporally valid and unconsumed at launch
- use macOS host-awake guard `caffeinate -dimsu`
- leave the runtime terminal untouched until the wrapper visibly returns or terminates
- no automatic retry, manual rerun, restart, resume, or successor under this authorization
- once the wrapper invokes the child path, this authorization is permanently consumed regardless of outcome
- preserve Source Governor and Central Scheduler ownership
- preserve PumpSwap protocol/account validation
- do not reintroduce Pump migration-registry confirmation for market-present candidates
- preserve current discovery/selection/source-budget and locked-capability rules

## Money-usefulness contribution

This authorization permits one bounded operational WINDOW_15M proof against the current clean post-DTW97 Git and DB state. The attempt can now test ordinary two-token memory-production progress while retaining the evidence, source, Scheduler, and safety controls required for useful clean memory.

## What this lane improves

- independently reviewed one-use provenance for the post-DTW97 successor attempt
- exact Git and DB binding
- explicit permanent non-reuse of DTW97 and all earlier authorizations
- bounded permission for ordinary WINDOW_15M operational proof only

## What this lane still does not unlock

This closeout does not claim runtime success and does not unlock WINDOW_1H/4H/12H/24H, retrieval, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper trade audits, PnL, live wallets, private keys, real funds, paid APIs, scoring/ranking/confidence systems, or embeddings/vectors. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Required post-invocation proof

Judge the attempt by durable terminal truth, not process exit code alone. Verify at minimum:

- exact one-use authorization consumption
- ordinary two-token WINDOW_15M scope
- discovery/selection and reserve truth
- source-budget and reconciliation accounting truth
- lifecycle/window terminal state and clean-memory truth
- Scheduler/discovery ownership and cleanup
- DB integrity and zero active/orphan residue after terminalization
- zero forbidden retrieval/decision/position/trade/audit/PnL deltas
- no lease-expiry or SQLite-contention recurrence

Use risk-based verification and expand only if the terminal evidence identifies a concrete blocker.

## Functionality Risks / Setbacks / Efficiency Blockers

- A new runtime blocker may still appear; authorization review PASS is not operational PASS.
- Process exit `0` alone is insufficient for operational success.
- Any Git or DB drift before launch must fail closed and requires renewed readiness/authorization work.
- Any terminal outcome after child invocation consumes this authorization permanently.
- The local reviewer required shell-safe extraction/status handling; this was tooling-only and created no production defect.
- No budget, tracking, source, Scheduler, memory, or safety rule may be relaxed merely to force a passing runtime.
- WINDOW_1H+ remains locked.

## Closeout decision

The fresh authorization is exact-one-use, temporally valid at independent review, provenance-bound, DB-bound, and unconsumed. One host-awake ordinary WINDOW_15M wrapper invocation is now permitted on the frozen preparation branch/HEAD, subject to the launch-time guards above.
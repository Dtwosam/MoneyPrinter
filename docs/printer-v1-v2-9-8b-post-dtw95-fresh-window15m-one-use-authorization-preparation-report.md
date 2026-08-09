# Printer V1 V2-9.8B Post-DTW95 Fresh WINDOW_15M One-Use Authorization Preparation

## Verdict

`V2_9_8B_POST_DTW95_FRESH_WINDOW_15M_ONE_USE_AUTHORIZATION_PREPARATION_READY`

This lane prepares, but does not itself create or consume, the next one-use ordinary two-token `WINDOW_15M` authorization. Runtime remains forbidden until a locally generated authorization package passes independent closeout.

## Frozen preparation baseline

- parent rereadiness closeout: `2713dfa897968154d38ff46b5e10ff8c8369b0cb`
- authoritative DB SHA-256 to bind: `59bb25aa71c1283a5086499053409082cb5f411ab4fb2b3e0bebd83da4a960ec`
- migration count: `53`
- migration head: `053_pilot_input_readiness_route_domain.sql`
- expected historical non-reusable authorization count: `24`

The twenty-fourth non-reusable authorization is the consumed DTW95 package:

`V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z`

All prior one-use authorizations remain non-reusable.

## Preparation requirements

The local preparation helper must fail closed unless all of the following hold:

- exact frozen preparation branch/head
- tracked/index Git state clean; retained untracked operator evidence is not deleted or mutated
- authoritative DB identity matches the rereadiness closeout baseline before package creation
- migration ledger guard passes in both prepare and review modes
- zero active operational residue
- source contract READY with zero external requests
- concrete ordinary `WINDOW_15M` composition READY
- runtime dependencies READY
- holder budget READY
- historical paper-audit baseline preserved
- all twenty-four historical one-use authorization IDs are excluded from reuse
- no existing fresh authorization directory conflicts with the new identity
- no application marker is created
- no Printer or Scheduler runtime starts
- no `WINDOW_15M` starts
- no DB change occurs during preparation

The package must bind exactly one new authorization ID, its final authorization SHA-256, the frozen Git branch/head, the current authoritative DB identity, and a pre-marker provenance manifest.

## Runtime requirements retained for later invocation

If and only if the independently reviewed package later permits runtime:

- invoke exactly once;
- run under the macOS host-awake guard (`caffeinate -dimsu`);
- preserve Source Governor and Central Scheduler ownership;
- keep PumpSwap protocol/account validation;
- do not require redundant Pump migration-registry membership for market-present candidates;
- do not widen campaign lease/heartbeat durations;
- no automatic retry, manual rerun, restart, resume, or successor;
- treat the authorization as permanently consumed after the first invocation regardless of outcome.

## Money-usefulness contribution

A fresh authorization package gives Printer one tightly bounded chance to prove that the repaired operational path can finish two trustworthy 15-minute observation lifecycles without weakening evidence, source, Scheduler, or memory-safety controls.

## What this lane improves

- Binds the next attempt to the repaired code lineage and current authoritative DB identity.
- Prevents reuse of the DTW95 authorization and all earlier one-use packages.
- Preserves deterministic pre-runtime readiness and provenance checks.

## What this lane does not unlock

Preparation alone does not authorize runtime and does not unlock retrieval, decisions, BUY/SELL/HOLD, positions, trade events, audits, PnL, longer memory windows, or any live-money capability.

## Proof/test required before completion

The local preparation must return a PASS package-review verdict with zero runtime/source/Scheduler/DB-write activity and `application_marker_created=false`. An independent authorization closeout is required before wrapper invocation.

## Functionality Risks / Setbacks / Efficiency Blockers

- The next operational attempt is still the first production proof of the cancellation-probe SQLite contention repair.
- A stale DB identity, Git drift, historical authorization reuse, or provenance mismatch must block before runtime.
- Host sleep remains a known operational hazard, so the later invocation must retain `caffeinate -dimsu`.

## Stop condition

Stop after package creation/review. Do not invoke the one-shot wrapper from this preparation lane.

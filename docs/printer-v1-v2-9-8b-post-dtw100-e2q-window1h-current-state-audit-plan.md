# Printer V1 V2-9.8B Post-DTW100 E2Q / WINDOW_1H Current-State Audit Plan

## Status

`AUDIT_ONLY_NOT_STARTED`

## Baseline

- Parent closeout: `059f4fad26d508b09cc361bc267049adc3cdb9ce`
- Parent verdict: `V2_9_8B_DTW100_WINDOW_15M_CLEAN_MEMORY_CAMPAIGN_CLOSEOUT_PASS`
- Authoritative DB trust anchor: `6ce0e27332427243cffd055c41de58408f46dbcd84d43a764bf1764915a176fb`
- DB migrations/head: `54` / `054_pre_lifecycle_discovery_refresh_wait.sql`

## Goal

Perform the audit/readiness step required by the active build order before any further `WINDOW_1H` proof attempt. Determine from current source, tests, and historical X14 evidence whether E2Q still blocks valid `WINDOW_1H` evidence only because of a `WINDOW_15M`-only assumption, and map every current 15m-only assumption that would require design before repair.

This is the current-state application of V2-6A. It does not presume that the historical blocker is unchanged.

## Allowed

- static source inspection;
- current test inspection;
- historical X14/E2Q artifact review;
- read-only authoritative DB inspection only if needed to verify current clean-memory identities;
- focused zero-I/O tests only where static inspection cannot establish current behavior;
- audit documentation.

## Not allowed

- production-code changes;
- migration changes;
- live source/provider/RPC calls;
- Scheduler runtime;
- authoritative DB mutation;
- memory generation;
- authorization creation/consumption;
- wrapper invocation;
- `WINDOW_15M` or `WINDOW_1H` runtime;
- 4h/12h/24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL.

## Required audit questions

1. What is the current E2Q owner/module/function and exact call chain?
2. Does current E2Q still hard-require `WINDOW_15M`? Locate every enforcing condition.
3. Which E2Q invariants are genuinely window-kind-independent and must remain unchanged?
4. Which 15m assumptions are cadence/coverage/identity specific and require a window-kind-specific 1h contract?
5. Does any current code already contain dormant/partial `WINDOW_1H` support?
6. Can `WINDOW_5M_MICRO_EVENT` remain explicitly invalid as a main outcome window under the same architecture?
7. What exact historical X14 Attempt 3C evidence reached the E2Q blocker, and what was still unproven?
8. What minimum design would allow real 1h evidence without fabricating 1h from 15m or weakening dirty/incomplete-data gates?
9. What tests already protect current 15m behavior, and what focused tests would be required before implementation?
10. Is a repair actually required, or has later work already superseded the historical blocker?

## Acceptance

Return one of:

- `E2Q_WINDOW_1H_REPAIR_DESIGN_REQUIRED`
- `E2Q_WINDOW_1H_REPAIR_ALREADY_SUPERSEDED_WITH_PROOF`
- `BLOCKED_CURRENT_STATE_INSUFFICIENT_TO_DESIGN`

A design lane is permitted only after this audit closes PASS.

## Locks preserved

All V1 locks remain unchanged. `WINDOW_1H` remains locked. `WINDOW_5M_MICRO_EVENT` remains support-only.

## Money-usefulness contribution

Prevents spending another long-window proof attempt on a known or misunderstood audit gate, while preserving the clean 15m foundation DTW100 just established.

## Functionality Risks / Setbacks / Efficiency Blockers

- Historical E2Q assumptions may have drifted; repairing from memory could modify the wrong seam.
- Generic acceptance of `WINDOW_1H` could admit dirty, incomplete, or fabricated long-window evidence.
- Reusing 15m thresholds blindly for 1h could create false clean memory.
- Over-broad testing would waste time; only minimum source-grounded checks belong in this audit.

## Stop condition

Stop after the audit closeout. No design implementation, runtime, authorization, or capability activation in this lane.

# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW52 Controlling Re-proof Authorization

Date: 2026-08-07

Parent: `DTW-34`

Reviewed baseline:

`14e39c2d19a793cb4f92c2e149025a1891ffd20d`

Authorization status:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW52_EXACTLY_ONE_LOCAL_FIXTURE_BACKED_ZERO_NETWORK_ATTEMPT_AUTHORIZED`

## Authorization

The operator authorizes exactly one fresh local Checkpoint 8 controlling re-proof after DTW-52.

The operator requested that the remaining Checkpoint 8 finish path be run together once. This authorization therefore permits one consolidated execution flow consisting of:

1. one fresh controlling C8 proof attempt;
2. immutable evidence freeze;
3. independent read-only inspection of the frozen result;
4. final Checkpoint 8 closeout only if every acceptance condition passes.

The consolidated flow does not permit a second proof attempt.

## Exact boundary

- exactly one attempt only;
- local Mac only;
- deterministic fixture-backed composition;
- zero provider/network attempts;
- disposable migrated DB only;
- real public composition owner;
- no authoritative DB use or mutation;
- atomic one-shot sentinel must prevent reuse;
- no retry, rerun, resume, restart, or successor under any outcome.

If the attempt blocks or fails:

- freeze the evidence;
- identify the first exact blocker read-only;
- stop;
- do not repair and rerun inside this authorization.

If the attempt is a PASS candidate:

- stop runtime;
- inspect the frozen evidence independently against the complete Checkpoint 8 acceptance law;
- create final Checkpoint 8 closeout only if every required condition is proven.

## Complete acceptance law

PASS requires all of the following, not merely `CAMPAIGN_PASS`:

- ordinary bounded `WINDOW_15M` public composition;
- campaign acceptance exactly `CAMPAIGN_PASS`;
- exactly two selected lifecycle tokens despite the four-deep reserve;
- exactly two campaign-owned terminal `WINDOW_15M` windows;
- both current-run windows E2Q-clean;
- one canonical `CLEAN_MEMORY` episode and fingerprint per window;
- `clean_memory_outcome_pass=True`;
- exact Source Governor / Central Scheduler / six-unit request and transport accounting;
- canonical terminal/report/artifact parity;
- cleanup and lease release;
- zero active, locked, orphan, or stranded residue;
- exact report-only replay with zero source calls, zero Scheduler runtime calls, and zero DB writes;
- disposable DB integrity `ok` and zero FK violations;
- zero provider/network attempts;
- zero protected downstream capability deltas;
- zero `WINDOW_1H+` objects/work;
- one-shot sentinel proving exactly one attempt.

## Locks preserved

This authorization is not permission for operational `WINDOW_15M` memory growth.

It does not authorize:

- `WINDOW_1H+`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live wallet;
- private keys;
- real funds;
- live execution;
- paid API dependencies.

`WINDOW_5M_MICRO_EVENT` remains support-only.

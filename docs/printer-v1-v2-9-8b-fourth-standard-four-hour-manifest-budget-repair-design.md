# Printer V1 V2-9.8B Fourth Standard Four-Hour Manifest/Budget Repair Design

## Verdict

`V2_9_8B_FOURTH_STANDARD_FOUR_HOUR_MANIFEST_BUDGET_REPAIR_DESIGN_PASS`

Baseline audit commit:

`3920a193cb73af2a5fd210364d48b8eb9908c91a`

This lane is design-only. It authorizes no source fetching, Scheduler/runtime execution, authoritative DB mutation, memory generation, authorization creation, or standard-four-hour run.

## Proven defects in scope

1. `COMMITTED_CODE_DEFECT__STANDARD_4H_ELIGIBILITY_MANIFEST_CURRENT_CLOSE_LOST_UPDATE`
2. `COMMITTED_CODE_DEFECT__STANDARD_4H_REPORTING_USES_ONE_TOKEN_BUDGET_SHAPE`

The fourth authorization `V2_9_8B_STANDARD_4H_AUTH_20260811T181829Z` is permanently consumed and must not be reused, rerun, resumed, restarted, or treated as authority for any successor run.

## Design decision 1 — preserve authoritative eligibility state after barrier release

The standard-four-hour handoff remains the sole owner that persists `standard_four_hour_eligibility` manifests. The loader remains strict: a partial, malformed, mismatched, or conflicting two-slot manifest set must still fail closed.

The runner must stop replacing the current successful `CONTINUATION_CLOSE.result_json` with the stale pre-barrier in-memory payload after `run_standard_four_hour_campaign_barrier(...)` returns.

### Required post-barrier write law

For a standard-four-hour `CONTINUATION_CLOSE`:

1. Complete and persist the physical 1h close normally so the barrier can see it as `SUCCEEDED`.
2. Run `run_standard_four_hour_campaign_barrier(...)`.
3. After the barrier returns, re-read the exact current close row from the DB using `run_id + step id`.
4. Parse the authoritative current `result_json` written after all barrier-owned manifest persistence.
5. Require identity consistency with the current step and require a mapping payload.
6. Add only `standard_four_hour_barrier` to that authoritative payload.
7. If a barrier field already exists, allow only exact idempotent equality; conflicting replay fails closed.
8. Persist the merged payload without replacing manifest content from the stale caller-local result.
9. Return/use the merged authoritative payload for later reporting.

A narrow helper in `one_command_15m_factory.py` is preferred, for example `_merge_standard_four_hour_barrier_result(...)`. It should update only the exact close row's `result_json` and `updated_at`; it must not create a second manifest owner.

### Expected behavior by close order

First close:
- barrier may return `AWAITING_PEER_FIRST_HOUR_CLOSE`;
- the barrier result is merged into the authoritative first-close payload;
- when the peer later releases the barrier, the handoff may add the first close's eligibility manifest without being erased.

Second close:
- barrier persists both exact eligibility manifests and plans the approved 4h subset;
- the caller then re-reads the second close and merges the release result into the already manifest-bearing payload;
- both manifests remain durable when the first 4h pre-step loader executes.

## Design decision 2 — standard-four-hour reporting uses the execution subset owner

Execution and reporting must use the same canonical standard-four-hour subset budget law.

For `standard_four_hour_campaign=True`, `_run_budgets(...)` must not fall back to the historical one-token `_cumulative_lifecycle_budget_for_run(...)` / one-lane phase ceiling shape.

### Required reporting law

When the exact standard manifest set is valid:

- derive cumulative request and Scheduler ceilings from the same standard subset budget owner used by execution;
- derive aggregate 4h phase request and Scheduler ceilings from only the eligible continuing slots;
- derive aggregate holder fallback allowance from those same eligible slots;
- compare aggregate two-token standard usage to aggregate standard ceilings;
- preserve exact per-token accounting separately; do not label total run usage as one token's usage.

The canonical arithmetic should remain beside `standard_campaign_lifecycle_budget(...)` in `one_token_4h_runtime.py`. Prefer exposing aggregate phase fields from that owner rather than duplicating sums inside reporting.

For two TRACK_NORMAL eligible slots the reporting projection must resolve to:
- cumulative governed request ceiling: 140;
- cumulative Scheduler ceiling: 114;
- aggregate 4h phase request ceiling: 78;
- aggregate 4h phase Scheduler ceiling: 68.

For one eligible slot, the projection includes both tokens' completed 15m/1h prefixes but only that slot's 4h suffix.

When the standard manifest set is partial/invalid, reporting must say the standard subset budget is unavailable/invalid with the exact reason. It must never silently substitute the historical one-token ceiling and report a fabricated numeric overrun.

Non-standard one-token/proof paths keep their existing budget/reporting law.

## Explicit non-goals / forbidden shortcuts

The implementation must not:

- weaken `load_standard_four_hour_eligibility_manifests(...)` to tolerate a partial set;
- increase the approved worst-case 236 governed-request or 210 Scheduler ceilings;
- increase per-token, holder-fallback, retry, endpoint-rotation, or provider allowances;
- change cadence policy or eligibility decisions;
- create a new DB table, schema migration, manifest format, or parallel persistence path;
- change Source Governor or Central Scheduler ownership;
- change source/provider contracts;
- change authorization semantics;
- unlock 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL;
- use a fifth live authorization as a debugging test.

## Expected implementation scope

Primary file:
- `src/printer_v1/operator_cli/one_command_15m_factory.py`

Only if needed to expose canonical aggregate standard phase fields:
- `src/printer_v1/operator_cli/one_token_4h_runtime.py`

Tests should be focused additions/updates around existing standard-four-hour barrier, subset budget, runner, and reporting contracts. No unrelated production refactor is approved.

## Minimum sufficient proof

Offline focused proof must establish all of the following before implementation closeout:

1. First successful 1h close waits for its peer without losing its payload.
2. Second successful 1h close releases the standard barrier.
3. Both durable close rows retain exact immutable `STANDARD_4H_ELIGIBILITY_V1` manifests after the caller's final post-barrier write.
4. `load_standard_four_hour_eligibility_manifests(...)` returns both manifests both immediately after barrier persistence and after final close-result persistence.
5. First 4h opening budget admission succeeds when the derived standard subset has capacity.
6. Deliberately partial manifest state still fails closed with scope `STANDARD_FOUR_HOUR_SUBSET`.
7. Conflicting or mismatched manifest identity remains fail-closed.
8. Both-eligible TRACK_NORMAL reporting produces cumulative 140/114 and aggregate phase 78/68.
9. One-eligible standard reporting derives the exact reduced subset without changing the completed two-token prefix.
10. Partial/invalid standard manifest reporting is unavailable/invalid, never one-token fallback.
11. Nearest historical non-standard one-token/proof budget reporting remains unchanged.
12. Tests perform no real source fetch and do not touch the authoritative operational DB.

Risk-based verification applies: run the new focused tests plus the nearest existing standard-four-hour budget/barrier regressions and compile/import checks. Do not run a broad full suite merely for this narrow implementation. Broader verification is reserved for implementation closeout/pre-live rereadiness.

## Money-usefulness contribution

The repair preserves a valid two-token 15m→1h learning path long enough to reach the approved 4h observation phase instead of wasting a one-use operational attempt on an internal lost update. Correct subset reporting also prevents legitimate bounded work from being mislabeled as budget-exceeded. This improves the reliability of longer-horizon memory growth; it does not claim profitability or authorize trading.

## What this lane improves

- one canonical durable eligibility state survives the peer-barrier release;
- execution-time subset reconstruction can see both approved slot manifests;
- reporting and execution share the same standard two-token budget authority;
- false one-token Scheduler overruns are removed without weakening ceilings.

## What this lane still does not unlock

- no fifth standard-four-hour authorization or run;
- no 12h/24h activation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions;
- no trade events;
- no paper trade audits;
- no PnL;
- no live wallet/signing/private keys/real funds.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Consequence | Control |
|---|---|---|
| Accept partial manifests | hides state loss and weakens fail-closed behavior | retain strict two-slot loader |
| Re-save stale local close payload | reproduces the fourth-attempt defect | authoritative DB re-read + narrow barrier merge |
| Add a second manifest writer | conflicting ownership/drift | handoff remains sole manifest owner |
| Duplicate standard budget arithmetic in reports | future execution/report drift | reuse/extend canonical subset budget projection |
| Compare aggregate two-token jobs to one-token phase ceiling | false budget overrun | aggregate eligible-slot phase ceilings |
| Inflate ceilings instead of fixing projection | weakens safety | preserve approved ceilings exactly |
| Use live proof before offline closeout | consumes another one-use attempt on unproven code | focused offline proof, closeout, rereadiness first |

## Next permitted lane

`V2-9.8B - Fourth standard-four-hour manifest/budget repair implementation`

Implementation is permitted only against this approved narrow design. It must stop after focused offline proof and implementation closeout. No authorization preparation or live standard-four-hour execution is part of the implementation lane.

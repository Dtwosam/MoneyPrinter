# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Eligible-Subset Handoff / Planning Repair Design

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_ELIGIBLE_SUBSET_HANDOFF_PLANNING_REPAIR_DESIGN_PASS`

Generalize the existing standard-four-hour campaign composer so the exact two owned campaign slots may produce an **explicit eligible continuation subset of 0, 1, or 2 slots** after the 1h->4h hard gates.

Do not create a second one-token standard planner. Do not reuse the historical one-token proof mode. Preserve one B1/B2 campaign composition owner, Source Governor, Central Scheduler, existing 4h cadence/close/memory owners, and the real-collection lock.

This design authorizes focused offline TDD implementation only. It does not authorize operational activation design, source fetching, runtime execution, authoritative DB mutation, real 4h collection, authorization creation, 12h/24h, retrieval, decisions, positions, PnL, wallet, signing or execution.

## Baseline

Design baseline:

`191cdc5c155d5f96571f6ceca9b3314c0d4c7e65`

Controlling audit:

`docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-operational-rereadiness-audit.md`

## 1. Keep two-slot campaign identity separate from continuation eligibility

The campaign still owns exactly two active token-slot records.

The standard composer continues to receive the exact two campaign candidate identity records so it can verify:

- campaign/run/cycle;
- both token slots;
- exact token/mint/pair/lifecycle identity;
- first-hour predecessor identity;
- tracking lane.

Add one explicit eligible-slot input, conceptually:

`eligible_token_slot_ids: Sequence[str] | None`

Rules:

- `None` preserves current compatibility and means both exact slots are eligible;
- explicit set may contain 0, 1, or 2 distinct owned slot IDs;
- unknown/duplicate slot IDs fail closed;
- omission from the eligible set is an explicit non-continuation outcome, not missing data;
- eligibility must never be inferred from price/outcome/learning-need inside B1/B2.

The later operational barrier remains responsible for deriving eligibility from the canonical hard-gate policy. This repair owns durable composition of the already-derived verdict, not policy invention.

## 2. Durable eligibility manifest without a migration

A legitimate one-slot standard plan must be distinguishable from accidental partial persistence.

Before B1/B2 creates any 4h successor, persist one exact eligibility manifest on each token's existing successful first-hour `CONTINUATION_CLOSE` run-step `result_json`.

Fixed manifest shape:

```text
standard_four_hour_eligibility:
  contract_version = STANDARD_4H_ELIGIBILITY_V1
  campaign_id
  campaign_run_id
  cycle_id
  token_slot_id
  token_id
  pair_id
  verdict = CONTINUE_TO_WINDOW_4H | BLOCK_CONTINUATION
  eligible = true | false
```

Requirements:

- exactly one successful first-hour close step for each campaign slot;
- exact step token/pair and `memory_window_id` must match the candidate's first-hour predecessor;
- the two manifests must cover the exact two campaign slots;
- eligible manifest set must equal the requested eligible-slot set;
- replay requires exact manifest equality;
- any existing conflicting manifest fails closed;
- manifest write and B1/B2 plan creation share the same caller-owned transaction so a planning/projection fault rolls all fresh subset-manifest/4h creation back together.

No new table/column is required.

## 3. Generalize B1 ownership handoff to the eligible subset

`persist_standard_four_hour_handoff_set(...)` remains the B1 owner.

Keep the exact two candidate identity set requirement, but create/advance 4h ownership only for candidate slots in `eligible_token_slot_ids`.

### Eligible slot

Preserve all current B1 continuation checks:

- slot currently `WINDOW_1H_CLOSED` on fresh handoff or exact `WINDOW_4H_CONTINUING` replay;
- exact terminal/bound clean eligible campaign `WINDOW_1H` predecessor;
- exact physical `WINDOW_1H` identity/quality;
- exact complete `WINDOW_1H_CLEAN_MEMORY` object;
- exact lifecycle/root/predecessor/cutoff identity;
- no competing 4h successor.

Fresh success creates one exact campaign `WINDOW_4H` and advances only that slot to `WINDOW_4H_CONTINUING`.

### Ineligible slot

Do not require it to satisfy continuation-quality gates it has already failed.

Require only:

- exact campaign-slot/token/pair/mint/lifecycle identity;
- no campaign `WINDOW_4H` successor for that slot;
- token state is not `WINDOW_4H_CONTINUING`;
- no conflicting successor ID exists.

Do not create a dummy 4h window and do not advance its token state.

### Read-back

Expected standard 4h successor set equals the explicit eligible-slot set exactly:

- 2 eligible -> exactly 2 successors;
- 1 eligible -> exactly 1 successor;
- 0 eligible -> exactly 0 successors.

Exact replay is idempotent. Changing the declared eligible subset after a durable manifest/plan exists fails closed.

## 4. Generalize the campaign lifecycle budget to prefix + eligible 4h suffix

The full campaign has already spent the two-token discovery/15m/1h prefix before the 1h->4h eligibility decision. A one-token eligible subset therefore must **not** use a one-token-from-launch budget.

Add one pure policy-derived owner conceptually:

`standard_campaign_lifecycle_budget(tracking_lanes, continuing_mask)`

Inputs:

- exact two tracking lanes;
- exact two booleans identifying which slots continue to 4h.

Budget formula:

```text
requests =
  global discovery allowance
  + both tokens' 15m snapshot/context prefix
  + both tokens' 1h snapshot prefix
  + 4h phase request ceiling only for eligible slots

scheduler =
  both tokens' discovery/handoff + 15m + 1h prefix
  + 4h phase scheduler ceiling only for eligible slots
```

Keep `standard_two_token_lifecycle_budget(lanes)` as a compatibility wrapper for `(True, True)`.

Under current committed policies, expected exact totals are:

| Lanes | Eligible 4h subset | Requests | Scheduler rows |
|---|---|---:|---:|
| FAST + FAST | none | 92 | 82 |
| FAST + FAST | either one FAST | 161 | 146 |
| FAST + FAST | both | 230 | 210 |
| FAST + NORMAL | none | 74 | 64 |
| FAST + NORMAL | FAST only | 143 | 128 |
| FAST + NORMAL | NORMAL only | 113 | 98 |
| FAST + NORMAL | both | 182 | 162 |
| NORMAL + NORMAL | none | 56 | 46 |
| NORMAL + NORMAL | either one NORMAL | 95 | 80 |
| NORMAL + NORMAL | both | 134 | 114 |

These must be derived from cadence/runtime policy, not hard-coded as policy magic numbers.

`real_collection_enabled` must remain false. Zero eligible slots must not become true through empty-set `all()` semantics.

## 5. Generalize B2 planning / Scheduler ownership

`plan_standard_campaign_4h_handoff(...)` remains the B2 composer.

It continues to require the exact two owned candidate records, plus the explicit eligible-slot set.

In one clean outer transaction:

1. validate exact two candidate/slot identities;
2. derive the two-slot prefix + eligible-4h budget;
3. persist/replay the exact two eligibility manifests;
4. call B1 with the same eligible-slot set;
5. for eligible slots only:
   - plan existing 4h phase primitives;
   - enqueue canonical Scheduler jobs;
   - project exact V2 stage-scoped campaign Scheduler ownership;
6. create no long work for ineligible slots;
7. verify exact subset state before commit.

Zero eligible slots are a valid no-4h outcome:

- eligibility manifests persist;
- zero 4h windows;
- zero long run steps;
- zero stage-scoped 4h Scheduler work;
- `planned=True`, `planned_jobs=0`, `continuation_count=0`, `no_op=True` is an acceptable explicit result shape.

A failure anywhere rolls back fresh manifests, B1 windows, token-state advancement, run steps, Scheduler jobs and campaign Scheduler-work projection together.

## 6. Subset-aware B2 read-back

Generalize `_standard_campaign_4h_plan_state(...)` so expected identities/counts come from the durable eligibility manifest / requested eligible set, not `2` as a constant.

For each eligible slot:

- exact one campaign 4h successor;
- exact policy-derived long-step count for that slot's lane;
- exactly one close;
- exact Scheduler job identity/count;
- exact V2 campaign Scheduler ownership count.

For each ineligible slot:

- zero campaign 4h successors;
- zero `LONG_CONTINUATION_*` run steps for its token/pair;
- zero stage-scoped 4h Scheduler work.

Aggregate counts equal the sum over eligible slots only.

No 12h/24h campaign window is permitted.

## 7. Make standard terminal validation use the durable eligibility manifest

The current standard terminal validator must not keep assuming two 4h windows after subset support exists.

Use the two durable first-hour eligibility manifests as the authoritative expected subset.

Activation rule:

- exact two manifest rows with `STANDARD_4H_ELIGIBILITY_V1` -> standard validator enabled;
- no manifest -> preserve historical one-token/legacy fallback behavior;
- partial/duplicate/conflicting manifest -> fail closed.

Expected terminal 4h window set equals the eligible manifest slots exactly.

### Two eligible

Preserve current two-window validation.

### One eligible

Validate the single exact 4h window with its own lane cadence, owned close, Scheduler/campaign-work terminal truth, physical memory and successful/blocked outcome. Require zero 4h window/work for the ineligible slot.

### Zero eligible

Standard validator remains enabled and can complete only when:

- zero 4h campaign windows;
- zero long run steps;
- zero stage-scoped 4h campaign Scheduler work;
- both eligibility manifests say `BLOCK_CONTINUATION`;
- no 12h/24h work exists.

Do not route a legitimate zero-eligible standard campaign through the historical one-token validator.

## 8. No activation change

This repair must not:

- add a public standard-4h command mode;
- reuse `four_hour_proof_mode` as production authority;
- modify the 15m one-shot wrapper/authorization schema;
- flip `WINDOW_4H.enabled_for_real_collection`;
- run sources or Scheduler runtime;
- create 12h/24h work.

Operational activation design remains a later lane after this repair closes and rereadiness is repeated.

## TDD / minimum sufficient proof

Create focused RED tests before production edits.

Minimum GREEN proof:

1. existing all-valid two-token B1/B2 tests remain green with default/all-eligible behavior;
2. A blocked / B eligible -> only B campaign 4h successor, long run steps and exact stage-scoped Scheduler ownership;
3. B blocked / A eligible -> symmetric result;
4. zero eligible -> durable two-slot eligibility manifest, zero 4h windows/jobs/work;
5. ineligible slot never advances to `WINDOW_4H_CONTINUING` and receives no dummy successor;
6. one-slot replay is idempotent with no duplicate windows/jobs/work;
7. requested subset drift after durable plan/manifest fails closed;
8. injected planning/projection failure rolls back fresh manifests plus all attempted subset 4h state;
9. B1 read-back rejects a foreign/competing successor on an ineligible slot;
10. exact current policy-derived subset budget totals above are proven;
11. standard terminal validator accepts one eligible terminal 4h lifecycle and zero-eligible clean no-op closeout;
12. terminal validator rejects missing/foreign/extra 4h ownership relative to the manifest;
13. all-valid mixed FAST/NORMAL terminal validation remains green;
14. token-local continuation hard-gate test still proves blocked A does not change eligible B's policy verdict;
15. no 12h/24h successor;
16. real 4h collection remains disabled;
17. directly affected collection/fairness/close/memory/terminal regressions remain green;
18. compile and `git diff --check` pass.

Use risk-based verification. No broad unrelated repository suite is required until the subset repair closeout.

## Expected production scope

Expected narrow production files:

- `src/printer_v1/operator_cli/campaign_ownership.py` — B1 subset ownership/read-back;
- `src/printer_v1/operator_cli/one_token_4h_runtime.py` — subset budget, eligibility manifest, B2 subset planning/read-back;
- `src/printer_v1/operator_cli/one_command_15m_factory.py` — manifest-aware standard terminal validation only.

No schema/migration/source-provider file is expected.

## Money-usefulness contribution

This repair prevents one invalid token from suppressing the valid peer's first-four-hour observation. It also prevents accidental partial persistence from masquerading as an intentional subset by making the exact 4h eligibility set durable.

The result is cleaner, less behavior-biased memory growth without weakening hard gates or inventing a trade signal.

## What remains locked after repair PASS

Even after subset implementation/proof PASS:

- operational standard-4h activation design remains pending a repeated rereadiness review;
- real 4h collection remains disabled;
- public command/wrapper/authorization changes remain locked;
- 12h/24h remain locked;
- retrieval, decisions, BUY/SELL/HOLD, positions/trades/audits/PnL remain locked;
- wallets, signing, live execution, real funds remain prohibited.

## Functionality Risks / Setbacks / Efficiency Blockers

- Missing-candidate semantics must never substitute for explicit eligibility; always keep the exact two owned candidates plus an explicit eligible subset.
- Budget calculation must retain both tokens' already-consumed 15m/1h prefix even when only one continues to 4h.
- A zero-eligible campaign needs durable manifests or final validation cannot distinguish legitimate no-op from lost work.
- Ineligible slots may have different correct post-1h states depending on the hard gate; the B1 repair must only prohibit `WINDOW_4H_CONTINUING`/4h successor rather than fabricate a new terminal state.
- Existing historical one-token proof mode remains separate from a standard one-eligible campaign.
- Manifest JSON must be merged without destroying existing first-hour close result evidence.
- Partial manifest persistence must roll back with plan creation; otherwise it could falsely authorize subset terminal validation.

## Next task

Focused offline TDD implementation of this eligible-subset repair only.

Stop after its bounded proof and closeout, then repeat operational standard-four-hour rereadiness before designing any activation change.

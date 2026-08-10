# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Operational Rereadiness Audit

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_OPERATIONAL_REREADINESS_BLOCKED_ELIGIBLE_SUBSET_IMPLEMENTATION_REPAIR_REQUIRED`

The current standard-four-hour codebase is **not yet ready to enter operational activation design**.

The previously proven all-valid two-token path remains useful and valid evidence, but this rereadiness audit found one design-conformance gap that the overall integration proof did not exercise: the adopted policy requires 4h continuation independently for each token that passes the hard gates, while the current B1/B2 standard handoff/planning owners require exactly two continuing candidates and reject a one-token eligible subset.

That means a token-local first-hour hard-gate failure can incorrectly prevent its otherwise-valid peer from receiving the standard 4h continuation promised by the adopted design.

This is a production implementation gap, not an activation-policy detail. It must complete its own audit/design/implementation/focused-proof/closeout cycle before operational rereadiness is re-run.

Separately, the current public operational command, one-shot wrapper/authorization contract, Git-manifest mode binding, duration/resource envelope and real-4h cadence lock are still 15m/legacy-proof shaped. Those activation-envelope gaps remain blocked behind the eligible-subset repair and are recorded here for the later rereadiness/design sequence.

This audit is read-only. It authorizes no code change, source call, Scheduler/runtime execution, authoritative DB mutation, memory generation, real 4h collection, authorization creation, 12h/24h work, retrieval, decisions, positions, PnL, wallet, signing or execution.

## Audit baseline

Exact repository baseline:

`1d942697e83ae7e14a7ce1b51dd89ed6c05de365`

Subject:

`Close standard four-hour campaign integration implementation proof`

The prior closeout verdict was:

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_CAMPAIGN_INTEGRATION_IMPLEMENTATION_PROOF_PASS`

Its exact-HEAD 110/110 proof remains evidence for the all-valid two-token standard path and the directly affected first-hour/one-token regressions. This audit does **not** claim those tests were false. It identifies a design-required branch that the proof did not include.

## 1. Adopted per-token continuation law

The controlling standard-four-hour design is explicit:

- for every otherwise-valid token, a genuine eligible first-hour close normally continues to `WINDOW_4H`;
- hard gates still apply independently;
- the handoff is defined **for each continuing token**;
- standard-four-hour policy applies independently to both active slots when both remain valid;
- a token-local failure blocks/terminalizes only that token unless shared DB/lease/integrity/budget safety is compromised.

The existing pure policy tests already demonstrate this required branch: when token A has `token_budget_available=False`, A returns `BLOCK_CONTINUATION` while token B still returns `CONTINUE_TO_WINDOW_4H`.

Therefore the campaign composition layer must be able to create/plan the 4h successor set for either:

- both eligible tokens; or
- exactly one eligible peer when the other token fails a token-local 1h->4h hard gate.

Zero eligible tokens should create no 4h successor.

## 2. Blocker — B1 handoff requires exactly two candidates

`campaign_ownership.persist_standard_four_hour_handoff_set(...)` currently:

- rejects `len(candidates) != 2`;
- requires the campaign to contain the exact two-slot ownership set;
- requires candidate slot IDs to cover **both** token slots;
- verifies exactly two `WINDOW_4H` successor rows;
- returns `continuation_count = 2`.

This is correct for the all-valid two-token proof shape but not for the adopted token-local hard-gate law.

A valid one-token subset cannot pass B1 today.

## 3. Blocker — B2 planner requires exactly two candidates

`one_token_4h_runtime.plan_standard_campaign_4h_handoff(...)` currently begins with:

`if len(candidates) != 2: raise ValueError("standard four-hour campaign requires exactly two candidates")`

Its plan-state verifier also assumes:

- two 4h campaign windows;
- the full candidate set;
- total planned/owned work for that exact two-window set.

So even if B1 were loosened independently, B2 would still reject the valid peer-only continuation branch.

This must be repaired as one coherent eligible-subset composition contract, not by bypassing B1 or manually enqueueing a peer's long jobs.

## 4. Why this blocks operational activation design

The missing branch is not a rare optional optimization. It is required by:

- the adopted hard-gate policy;
- token-local failure isolation;
- the money-usefulness goal of not losing a valid token's first-four-hour evidence merely because its peer became invalid;
- the no-hidden-campaign-wide-failure rule.

Activating real 4h collection before this repair would create a policy mismatch:

```text
policy: valid peer continues
implementation: standard composer rejects because only one candidate remains
```

The safe response is to repair the implementation first, then repeat operational rereadiness.

## 5. Qualification of the prior overall implementation/proof closeout

The prior overall closeout remains trustworthy for what it actually proved:

- both otherwise-valid tokens continue;
- FAST/FAST, FAST/NORMAL and NORMAL/NORMAL capacity derivation;
- exact two-token B1/B2 handoff/planning/Scheduler ownership;
- collection state/accounting/fairness;
- token-local failure during the 4h phase;
- physical close/memory/terminal reconciliation;
- no 12h/24h successor;
- all real-collection locks.

It must **not** be used as evidence that the standard campaign is fully design-conformant for the one-of-two eligible 1h->4h branch.

Until the subset repair passes, the earlier `...IMPLEMENTATION_PROOF_PASS` is qualified as:

`PASS_FOR_ALL_VALID_TWO_TOKEN_PATH__NOT_SUFFICIENT_FOR_OPERATIONAL_ACTIVATION`

No historical evidence is deleted or rewritten.

## 6. Operational DB/schema readiness — last verified compatible, fresh host check still required later

The last authoritative post-DTW100 trust anchor records:

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`;
- migration count/head: `54 / 054_pre_lifecycle_discovery_refresh_wait.sql`;
- integrity: `ok`;
- foreign-key violations: `0`;
- sidecars: none;
- zero active/locked Scheduler residue after DTW100;
- lease released and lease lock absent.

Migration 050 is already included in that migration-54 database and provides the V2 stage-scoped campaign Scheduler ownership columns/invariants used by B1/B2 and the current 4h implementation.

No new migration was required by the standard-4h implementation work.

Therefore there is **no presently identified schema-migration blocker** for the subset repair.

However GitHub evidence cannot prove the current operator-machine DB bytes/process/lease state at this moment. Before any later authorization, a fresh operator-host read-only check must re-establish:

- exact DB identity;
- `54/54` migration agreement unless a later approved migration legitimately changes it;
- integrity/FK/sidecars;
- zero active campaign/run/cycle/Scheduler/proof/factory work;
- zero stale lease/lock conflict.

This audit does not infer current host quiescence from the historical DTW100 closeout.

## 7. Existing operational activation-envelope blockers retained for later rereadiness

Even after the eligible-subset repair, activation is not automatically ready.

### Public operational command remains 15m / old-proof shaped

`operational_memory_factory_command.py` currently exposes public modes only for:

- `preflight-only`;
- `run` (ordinary 15m).

The hidden selective-1h proof path is not production authority. There is no standard-four-hour operational mode/policy.

Current ordinary-run policy still locks `WINDOW_1H/4H/12H/24H`.

### Wrapper / authorization remains 15m-only

`window_15m_one_shot_wrapper.py` validates `PRINTER_V1_WINDOW_15M_FINAL_AUTHORIZATION_V2`, requires main window `WINDOW_15M`, and requires 1h/4h/12h/24h to remain locked.

The DTW100 authorization was consumed exactly once and is permanently non-reusable. Its Git and DB bindings are historical and cannot authorize a future 4h run.

A later standard-four-hour run needs its own exact one-use authorization contract; the 15m wrapper must not be weakened into accepting a different lifecycle silently.

### Manifest / child-terminal mode binding lacks standard 4h

The current Git provenance/public-command mode contract is bound to the existing preflight/run shapes. A later activation design must add exact standard-4h mode identity through manifest, child terminal and authorization review rather than hiding 4h behind legacy proof flags.

### Factory activation seam remains historical-proof shaped

The main factory currently enables long planning through the legacy branch:

- `continuous_four_hour=True`;
- `four_hour_proof_mode=True`;
- `plan_current_run_4h(...)`.

The adopted design explicitly says historical `four_hour_proof_mode` must never silently become production authority.

The current public runtime does not yet invoke the new standard campaign handoff/planning owner at the operational 1h barrier.

After the eligible-subset repair, a later activation design must define one explicit operational standard-4h seam that invokes the standard composer for the exact eligible token subset rather than the historical one-token proof planner.

### Real cadence remains deliberately disabled

Both FAST and NORMAL `WINDOW_4H` cadence policies still have:

`enabled_for_real_collection=False`

This is correct and must remain false through the subset repair and subsequent rereadiness/design work until the explicitly approved activation implementation/proof step.

`WINDOW_12H` and `WINDOW_24H` remain disabled.

## 8. Resource-envelope status

The implementation already derives the standard first-four-hour lifecycle ceilings:

| Eligible two-token lane shape | Requests | Scheduler rows |
|---|---:|---:|
| FAST + FAST | 230 | 210 |
| FAST + NORMAL | 182 | 162 |
| NORMAL + NORMAL | 134 | 114 |

For a one-token eligible subset, the later repair/activation design must derive the corresponding exact one-token campaign envelope from existing policy components rather than reusing a two-token ceiling as an unexplained constant.

Operational pre-lifecycle acquisition remains a separate bounded contract (historically a 900-second acquisition horizon and cumulative 30-operation discovery budget in the DTW100 authorization path). Do not silently conflate that acquisition accounting with the post-supply lifecycle request ceiling.

A later activation design must explicitly define both accounting scopes and prove no double charge or unaccounted source operation.

## 9. Duration-envelope status

The current public command has 15m/first-hour-oriented duration policies and no standard-four-hour operational duration contract.

The factory's legacy continuous path requires enough post-supply time for:

- 15m main lifecycle;
- remainder to the 1h checkpoint;
- 10,800-second 1h->4h continuation;
- plus the command's required terminal/cleanup margin.

The later activation design must derive the exact operational duration from committed cadence policy and established cleanup semantics. It must not copy a historical proof duration blindly.

The pre-lifecycle acquisition horizon remains separate.

## 10. Source Governor / Scheduler ownership status

Positive readiness facts:

- all external source work remains Source-Governed;
- all lifecycle work remains Central-Scheduler-owned;
- B2 exact stage-scoped Scheduler projection is implemented;
- long-step reservation accounting is implemented;
- token-local 4h failure isolation is implemented;
- shared safe-stop cleanup is implemented;
- standard 4h fairness is categorical and proven;
- exact terminal work reconciliation is implemented.

The subset repair must preserve those owners. It may not solve cardinality by directly creating unowned Scheduler rows or a private source loop.

## Money-usefulness contribution

This audit prevents Printer from activating a superficially complete two-token 4h path that would throw away a valid peer's long-horizon memory whenever the other token fails an independent hard gate.

Repairing the eligible-subset path preserves unbiased first-four-hour observation for every token that remains valid while still failing closed for the token that became invalid.

The audit itself creates no market evidence and proves no profitability.

## What this audit improves

- identifies a real design-conformance gap before activation;
- separates all-valid two-token proof coverage from one-of-two eligible policy coverage;
- confirms no current schema migration is known to be required;
- preserves the deliberate real-4h cadence lock;
- records the later operational-envelope gaps without skipping the implementation repair that must precede them.

## What remains locked

Still locked:

- eligible-subset production repair until its design is approved;
- operational activation design until that repair/closeout passes;
- real `WINDOW_4H` collection;
- cadence-policy enablement;
- fresh standard-4h authorization;
- source fetching / operational Scheduler runtime in this lane;
- authoritative DB mutation;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, audits, PnL;
- wallets, private keys, signing, live execution, real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors.

## Minimum proof required for the subset repair

A later focused offline implementation proof must establish at minimum:

1. both eligible tokens still produce the exact two-window B1/B2 plan and existing all-valid proofs remain green;
2. token A blocked by a token-local 1h->4h hard gate + token B eligible creates/plans **only B's** exact campaign `WINDOW_4H` and long Scheduler ownership;
3. symmetric B-blocked/A-eligible behavior;
4. zero eligible tokens creates zero 4h successors/jobs/work rows;
5. the blocked/non-continuing slot remains in its correct terminal/review state and is not advanced to `WINDOW_4H_CONTINUING`;
6. no competing/foreign 4h successor can already exist on the non-continuing slot;
7. exact one-candidate replay is idempotent with no duplicate window/jobs/work rows;
8. one-candidate partial failure rolls back only the attempted standard handoff composition and leaves peer/blocked-slot truth consistent;
9. one-token subset uses that token's own FAST/NORMAL cadence and policy-derived source/Scheduler ceilings;
10. no 12h/24h successor is created;
11. real 4h collection remains disabled;
12. Source Governor/Central Scheduler ownership, fairness, failure and terminal regressions remain healthy.

## Functionality Risks / Setbacks / Efficiency Blockers

- Simply changing `len(candidates)==2` to `>=1` is insufficient: current B1 read-back and candidate-slot coverage assertions also hard-code the two-slot continuation set.
- Reusing the two-token budget blindly for one eligible token would hide the real resource envelope and weaken later authorization review.
- A one-token eligible subset must not be confused with the historical one-token proof mode; it remains a standard campaign token-local outcome under the new policy.
- The non-continuing slot must not receive a fabricated 4h window merely to satisfy two-slot read-back checks.
- Partial standard ownership must remain fail-closed; exact subset identity must be explicit so a missing legitimate peer is distinguishable from accidental partial persistence.
- The later activation design still has substantial command/wrapper/authorization work after this repair; this audit does not imply activation will immediately pass afterward.

## Next permitted task

Begin a separate **Standard Four-Hour Eligible-Subset Handoff / Planning Repair Design**.

That design must generalize the standard B1/B2 composition to the exact eligible subset of the two owned campaign slots (one or two candidates), preserve zero-candidate no-op truth, retain exact policy-derived capacity and all existing ownership/safety locks, and keep real 4h collection disabled.

Do not begin operational activation design until the subset repair has its own implementation/proof closeout and operational rereadiness is re-run.

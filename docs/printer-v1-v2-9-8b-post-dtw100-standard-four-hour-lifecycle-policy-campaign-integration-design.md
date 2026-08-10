# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Lifecycle Policy and Campaign-Integration Design

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_LIFECYCLE_POLICY_AND_CAMPAIGN_INTEGRATION_DESIGN_PASS`

Adopt the following bounded observation policy for the next implementation lane:

```text
validly activated token
-> WINDOW_15M checkpoint
-> standard hard-gated continuation to full first hour
-> WINDOW_1H checkpoint
-> standard hard-gated continuation to full first four hours
-> WINDOW_4H checkpoint
-> stop automatic continuation
```

`WINDOW_15M` and `WINDOW_1H` outcomes are evidence checkpoints, not behavior-based qualification gates for the remaining first-four-hour observation. `WINDOW_4H -> WINDOW_12H` remains locked/selective and is not part of this design.

This design authorizes no code, real-collection activation, source fetching, runtime, authorization creation, authoritative DB mutation, operational memory generation, retrieval, paper decision, position, trade, PnL, wallet, signing, or execution.

## Baseline and controlling audit

- Design baseline: `74bd2b48f4a1a0cd8d87e3696773d038ce59e2ca`.
- Controlling audit: `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-current-state-audit.md`.
- Audit verdict: `V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_LIFECYCLE_AUDIT_BLOCKED_CAMPAIGN_INTEGRATION_POLICY_AND_TWO_TOKEN_CAPACITY_DESIGN_REQUIRED`.

V2-9 already proved one-token 4h feasibility. Do not repeat that proof merely to re-establish that 4h memory can work.

## 1. Policy amendment

For every otherwise-valid token already inside the bounded main lifecycle, a genuine eligible first-hour close normally continues to `WINDOW_4H`.

The following have **no authority** to stop or authorize 1h->4h observation:

- 1h outcome label;
- `NO_PUMP`, `CONSOLIDATION`, pump/dump direction, round trip, survival label, or profitability;
- trajectory/transition category by itself;
- manipulation label by itself;
- `learning_need` or absence of `learning_need`;
- `WINDOW_5M_MICRO_EVENT`;
- score, rank, confidence, weighting, or prediction.

This removes behavior-conditioned sampling from the first four hours while preserving all operational validity gates.

## 2. Hard gates retained

A token does **not** continue merely because the policy is standard. The 1h->4h handoff must fail closed when any required condition fails:

- exact campaign/run/cycle/token-slot/token/mint/pair/lifecycle identity;
- exact genuine `WINDOW_1H` predecessor and exact predecessor linkage;
- predecessor window closed and evidence complete;
- clean/eligible predecessor memory quality under the current continuation contract;
- `CLEAN_DATA`, `do_not_train=0`, freshness within contract;
- governed provenance traceable through Source Governor;
- mandatory safety context present and acceptable;
- exact continuity eligible;
- campaign is running/eligible;
- shared DB, lease, and integrity health;
- token/campaign/source/Scheduler/storage budget available;
- token not cancelled or terminal;
- exact one-use execution authority when an operational proof is later approved.

Dirty, blocked, stale, mismatched, or incomplete first-hour evidence remains dirty/blocked and cannot be relabelled clean to obtain 4h continuation.

## 3. Continuation-policy implementation rule

`src/printer_v1/scheduler/token_local_continuation.py` remains the pure policy owner.

The implementation should create a standard-four-hour transition marker analogous to the standard-first-hour marker and preserve the current hard-gate evaluation order.

After all hard gates pass:

- `WINDOW_15M -> WINDOW_1H`: bounded token budget required -> `CONTINUE_TO_WINDOW_1H`;
- `WINDOW_1H -> WINDOW_4H`: bounded token budget required -> `CONTINUE_TO_WINDOW_4H`;
- no `learning_need` qualification on either transition.

The existing learning-need vocabulary remains historical/future-use evidence and may still be used later for 4h->12h design. It must not be deleted merely to implement this policy.

No 4h->12h transition is added here.

## 4. Exact campaign-owned 1h->4h handoff

The new operational handoff must start only from a Checkpoint-6 reconciled token:

- campaign token state = `WINDOW_1H_CLOSED`;
- exact campaign `WINDOW_1H` is terminal and bound to its physical first-hour row;
- exact first-hour clean/eligible predecessor object is available for the continuation contract.

For each continuing token, atomically:

1. create one exact campaign `WINDOW_4H` with:
   - same campaign/run/cycle/token slot/token/pair/lifecycle;
   - exact predecessor campaign `WINDOW_1H` identity;
   - root 15m lifecycle identity;
   - fixed 4h checkpoint cutoff;
2. advance token `WINDOW_1H_CLOSED -> WINDOW_4H_CONTINUING`;
3. plan exact long-window run steps;
4. enqueue their Central Scheduler jobs;
5. project every job through the stage-scoped campaign Scheduler-work owner;
6. verify exact counts/identity before commit.

Any partial creation, duplicate successor, mismatched predecessor, Scheduler enqueue failure, campaign-work projection failure, or identity conflict rolls back/fails closed. A repeated exact handoff is idempotent and creates no duplicate window/jobs.

No direct private source loop is allowed.

## 5. Reuse existing 4h cadence and physical close owners

Do not rewrite the proven 4h cadence/continuity/quality machinery.

Reuse:

- `WINDOW_4H` cadence policies;
- exact current-run 1h predecessor resolution;
- fixed 10,800-second continuation deadline;
- `LONG_CONTINUATION_SNAPSHOT` / `LONG_CONTINUATION_CLOSE` step semantics;
- continuity evaluator;
- forced closing-snapshot rule;
- 4h physical-window close;
- E2Q genuine-4h validation;
- Lane Q 4h cadence/coverage;
- E2Z atomic clean episode+fingerprint promotion.

The old `one_token_4h_runtime.py` may be refactored only as necessary to expose reusable phase planning/close primitives. Do not create a second 4h collector.

## 6. Two-token fairness and scheduling

Standard-four-hour policy applies independently to both active token slots when both remain valid.

Scheduler order remains categorical:

1. imminent main-window close, earliest deadline first;
2. overdue evidence-gap/safe-stop work;
3. token receiving less service in the current fairness round;
4. older Scheduler-work identity;
5. stable slot order only as final tie-breaker.

Each fairness round must offer both eligible 4h tokens service before either receives a second ordinary non-close long-window unit. Close work may preempt ordinary work but must not permanently starve the peer.

A token-local failure blocks/terminalizes only that token unless shared DB/lease/integrity/budget safety is compromised.

## 7. Policy-derived resource ceilings

Do not copy the historical one-continuer compressed-proof ceiling.

At implementation time, derive the full campaign ceiling from the actual selected lanes and committed cadence/runtime policies.

For token `i`, current phase components are:

```text
request_i =
  WINDOW_15M minimum snapshots
  + 15m context allowance
  + WINDOW_1H minimum snapshots
  + WINDOW_4H phase request ceiling

scheduler_i =
  1 discovery/handoff allowance
  + WINDOW_15M minimum snapshots
  + WINDOW_1H minimum snapshots
  + WINDOW_4H phase scheduler ceiling
```

Run request ceiling:

```text
global discovery allowance + sum(request_i)
```

Run Scheduler ceiling:

```text
sum(scheduler_i)
```

Under the currently committed policies, the design targets are:

| Two-token lane combination | Request ceiling | Scheduler-row ceiling |
|---|---:|---:|
| FAST + FAST | 230 | 210 |
| FAST + NORMAL | 182 | 162 |
| NORMAL + NORMAL | 134 | 114 |

These values must be calculated from policy at runtime/configuration construction, not embedded as unexplained magic constants. If the underlying cadence/context/fallback contract changes, the derived ceiling changes with it.

Per-token 4h phase ceilings remain today's committed values unless a later explicit design changes them:

- FAST: 69 source operations / 64 Scheduler rows;
- NORMAL: 39 source operations / 34 Scheduler rows;
- zero automatic retries;
- no endpoint rotation;
- holder fallback limit remains the already-approved bounded contract.

Implementation must verify Source Governor reservation accounting so all context/snapshot operations are charged exactly once.

## 8. Campaign Scheduler-work ownership

Every 4h Scheduler job must have an exact stage-scoped campaign Scheduler-work projection carrying:

- campaign/run/cycle;
- token slot;
- exact campaign `WINDOW_4H`;
- Scheduler job id;
- work intent / long-window step identity;
- deadline;
- V2 ownership contract version;
- terminal Scheduler truth synchronization.

No 4h job may exist as operational campaign work only in `printer_scheduler_jobs` / run steps while absent from campaign ownership.

Campaign active-work reporting must count 4h work and prove zero active long-window work at terminal closeout.

## 9. Four-hour collection and failure behavior

For each token:

- opening 4h collection begins from the exact first-hour close boundary;
- snapshot cadence follows its lane's current 4h policy;
- no missing snapshot is interpolated;
- Source Governor reservation accounting is applied before each step;
- Scheduler claim/success/failure state is projected to campaign work;
- token-local failure cancels only that token's remaining long-window work;
- shared budget/DB/lease/integrity failure safely stops both;
- no automatic restart/successor campaign.

The 4h physical close must prove exact first snapshot, exact forced close snapshot, fixed deadline, token/pair identity, predecessor linkage, continuity, and cadence before creating/promoting memory.

## 10. Four-hour memory and terminal reconciliation

On successful physical close, reuse the existing 4h quality path:

```text
physical WINDOW_4H
-> E2Q
-> Lane Q
-> E2Z atomic clean object
```

Then reconcile exact campaign lifecycle truth using the Checkpoint-6 pattern:

| 4h result | Campaign `WINDOW_4H` | Token slot |
|---|---|---|
| exact eligible clean 4h episode | `CLEAN_PROMOTED` | `WINDOW_4H_CLOSED` |
| dirty/do-not-train/non-clean row | `DIRTY` | `WINDOW_4H_CLOSED` |
| valid close without clean object | `NO_PROMOTION` | `WINDOW_4H_CLOSED` |
| token-local execution failure | `BLOCKED` | `FAILED` |
| shared/run-wide safe-stop cancellation while active | `CANCELLED` | `MANUAL_REVIEW` |

Exact replay is idempotent; first terminal causes and memory bindings are immutable.

`WINDOW_4H_CLOSED` creates no 12h work in this lane.

## 11. Real-collection activation boundary

`enabled_for_real_collection=False` for `WINDOW_4H` is a deliberate current lock.

Implementation should **not** flip that flag at the beginning of the lane.

Order:

1. implement standard policy and campaign integration behind offline/proof boundaries;
2. run focused offline composition proof;
3. close implementation/proof;
4. conduct a separate 4h operational rereadiness review;
5. only if that passes, explicitly approve the narrow real-collection activation change and prove it;
6. only later prepare a fresh one-use operational authorization.

The historical `four_hour_proof_mode` must never silently become production authority.

## 12. Source-stack amendment

Current policy documents must be updated narrowly to establish:

- standard observation through 4h for otherwise-valid activated tokens;
- 15m and 1h behavior/outcome labels do not qualify continuation;
- hard gates still apply;
- automatic continuation stops after the 4h checkpoint;
- 12h/24h remain selective/locked;
- 5m remains support-only;
- real 4h collection remains locked until the later explicit activation boundary.

Historical V2-9.7C design/proof documents remain historical and must not be rewritten to pretend they originally specified this amendment.

## 13. TDD and proof plan

### Pure policy RED/GREEN

Prove at minimum:

- valid `WINDOW_1H -> WINDOW_4H` with `learning_need=None` continues;
- quiet/no-pump/consolidation outcomes continue with the same standard reason;
- transition outcomes receive no special continuation authority;
- token budget exhaustion blocks;
- identity/evidence/safety/continuity/cancellation failures still block;
- unsupported 4h->12h remains blocked/not implemented;
- 5m never authorizes 4h.

### Campaign composition RED/GREEN

Prove:

- both valid tokens can atomically acquire exact campaign `WINDOW_4H` successors;
- token state becomes `WINDOW_4H_CONTINUING` exactly once;
- exact predecessor identity is mandatory;
- every long job has exact campaign Scheduler-work ownership;
- mixed FAST/NORMAL plans produce exact policy-derived counts/ceilings;
- fairness services both tokens;
- close priority works without starvation;
- token-local failure isolates;
- shared stop cleans both;
- source reservations and Scheduler ceilings cannot be exceeded;
- exact 4h close reuses continuity/cadence/E2Q/Lane Q/E2Z;
- campaign 4h terminal state and token state reconcile atomically;
- no active 4h work remains after completion;
- no 12h jobs/windows are created;
- retrieval/decision/financial deltas remain zero;
- Checkpoints 1-6 and directly affected 4h proof regressions remain green.

Use minimum sufficient risk-based verification; do not run an unrelated full repository suite.

## Money-usefulness contribution

The policy captures delayed behavior that a one-hour selection gate would systematically miss while preserving strict evidence quality and capacity law. Two-token campaign integration makes that additional learning operationally trustworthy rather than merely creating more rows.

This improves future corpus usefulness for survival, collapse, revival, distribution, delayed pumps, round trips, and liquidity deterioration. It does not prove profitability or authorize any paper action.

## What this design improves

- removes first-hour behavior-conditioned sampling from the first four hours;
- converts proven one-token 4h primitives into an explicit two-token campaign design;
- preserves Source Governor/Scheduler ownership;
- derives resource ceilings from policy;
- defines exact 4h lifecycle truth and cleanup;
- stops scope at 4h.

## What remains locked

- no implementation in this design lane;
- no real 4h collection activation;
- no source fetching/runtime/authorization;
- no authoritative DB mutation or operational memory generation;
- no 12h/24h;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions/trades/audits/PnL;
- no wallet/private keys/signing/real funds/live execution;
- no paid APIs;
- no scoring/ranking/confidence/weighted logic;
- no embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Two-token full 4h tracking has substantially higher bounded resource cost than the historical one-continuer proof.
- The old proof runtime and new campaign path must not become duplicate collectors.
- Source-stack wording must be amended before code changes so agents do not follow conflicting selective-continuation law.
- Real-collection activation must remain last, not be used to make offline tests convenient.
- Campaign/Scheduler projection is mandatory; run-step-only long work is insufficient for operational ownership.
- Close deadlines for two long windows can coincide; fairness and close priority need explicit proof.
- Report-yield logic must use authoritative clean objects to avoid the historical 4h under-count.
- Current E2Q comments contain stale 4h-disabled wording; implementation should reconcile comments without changing the proven gate contract.
- 4h must not become a bridge to unapproved 12h/24h automation.

## Stop condition and next lane

After this design and the matching source-stack amendments pass static review, close the design/adoption lane.

Next permitted lane:

`V2-9.8B Post-DTW100 Standard Four-Hour Lifecycle Campaign Integration Implementation`

Implementation must begin with TDD RED and remain offline/proof-bounded. No live authorization is created automatically.

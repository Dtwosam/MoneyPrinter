# Printer V1 V2-9.8B Lane 3 Readiness Audit

## Post-1H Standard-4H Progression + Fault Preservation

Date: 2026-08-23
Starting HEAD: `30db8a89a761e3b1b894e393a9c70c46e84311c9`

## Verdict

`V2_9_8B_LANE3_POST_1H_STANDARD_4H_PROGRESSION_FAULT_PRESERVATION_READINESS_AUDIT_PASS_READY_FOR_DESIGN`

The audit is complete and a separate design lane is justified. The current
runtime has a real production route from committed first-hour closes to
Central-Scheduler-owned Standard-4H work, and the 4h execution path remains
Source-Governed. It is not safe to activate Cycle 3 or run another campaign.

The blocking runtime facts are:

- the progression barrier consumes successful run-step and physical-memory
  facts but has no durable progression-attempt/disposition owner before its
  all-or-nothing planning transaction;
- shared campaign, lease, integrity and budget inputs, plus token budget and
  token eligibility inputs, are synthesized as healthy/eligible rather than
  read from their production authorities at the barrier;
- a failed/cancelled first-hour close raises from the shared barrier instead of
  producing a token-local terminal non-eligibility disposition for the peer-
  preserving 0/1/2 subset contract;
- a barrier exception occurs after the successful first-hour step, Scheduler
  job, campaign work and campaign window have already committed, but the same
  step-level exception handler then rewrites that successful step and Scheduler
  job as failed; a secondary reconciliation exception can replace the original
  cause before the outer handler records only `SAFE_STOP_PREFLIGHT_FAILED`;
- no manifest plus no 4h window is treated by the standard terminal validator
  as “standard 4h disabled/complete”, so absence is not a truthful persisted
  distinction between never eligible and eligible-but-not-created; and
- the consumed 4/2/2 production run proves that two clean Cycle-1 first-hour
  closes can terminate with no 4h rows and no recoverable primary exception in
  final `fault_details`.

This PASS means the audit is sufficient to begin a separate design. It is not
a runtime-readiness PASS and grants no execution authority.

## Scope and evidence

This was static/read-only work. No provider, authoritative database, campaign,
Scheduler runtime, authorization, test fixture, or production row was used to
manufacture a transition.

Primary production sources inspected:

- `operator_cli/one_command_15m_factory.py`;
- `operator_cli/operational_standard_4h.py`;
- `scheduler/token_local_continuation.py`;
- `operator_cli/one_token_4h_runtime.py`;
- `operator_cli/campaign_ownership.py`;
- `operator_cli/operational_selective_1h.py`;
- `scheduler/scheduler.py`, `scheduler/_scheduler_base.py`, and
  `scheduler/contracts.py`;
- `operator_cli/campaign_full_run_accounting.py`;
- `operator_cli/final_campaign_report.py`;
- `operator_cli/unified_terminal_closure.py`; and
- migrations `032` and `050` for campaign/window/work persistence.

The consumed 4/2/2 forensic audit supplies the real production observation:
both Cycle-1 `WINDOW_1H` rows were `CLEAN_PROMOTED` with exact clean episodes,
zero `WINDOW_4H` rows were created, terminal truth collapsed to
`SAFE_STOP_PREFLIGHT_FAILED`, and final `fault_details` contained no primary
orchestration exception. The exact first failing historical call remains
missing evidence; this audit does not invent it.

## 1. Exact current production-path map

| Transition | Production owner and persisted authority | Scheduler ownership | Success | Failure / restart / isolation |
| --- | --- | --- | --- | --- |
| 1h collection plan | `_run_selective_1h_campaign_barrier` and `_plan_continuation_jobs` | `CONTINUATION_SNAPSHOT` uses `TRACK_FAST_1H`/`TRACK_NORMAL_1H`; all close phases use `MEMORY_WINDOW_CLOSE`; every row has exact V2 stage-scoped campaign work at `WINDOW_1H` | Exact step/job/work/window plan | Planning faults roll back; no automatic retry |
| 1h execution | the one-command factory Scheduler loop | Central Scheduler selects, claims and terminalizes each job | step `SUCCEEDED`, Scheduler `SUCCEEDED`, campaign work `SUCCEEDED` | ordinary blocked/technical failures are token-local, `max_retries=0`; pending sibling-token work remains selectable |
| 1h terminal bind | `_bind_owned_continuation_memory_window_at_close` -> `reconcile_1h_terminal_lifecycle` | executed while the claimed close-audit job is still owned | exact physical `WINDOW_1H` bound; campaign window terminal; slot becomes `WINDOW_1H_CLOSED` | exact window/slot failure or cancellation is durably terminalized with cause |
| progression invocation | one-command factory, immediately after the successful 1h close/audit commit | no separate Scheduler job represents the barrier itself | calls `run_standard_four_hour_campaign_barrier` after each committed 1h close | barrier exception is outside any dedicated progression owner |
| barrier release | `operational_standard_4h.run_standard_four_hour_campaign_barrier` | none until planning begins | both exact 1h close run steps are `SUCCEEDED`; then per-token hard gates return a 0/1/2 eligible subset | peer still pending returns `AWAITING_PEER_FIRST_HOUR_CLOSE`; failed/cancelled peer raises a shared exception |
| eligibility persistence and 4h handoff | `plan_standard_campaign_4h_handoff` plus `campaign_ownership.persist_standard_four_hour_handoff_set` | enqueue through the Central Scheduler API; project every job to exact V2 stage-scoped `WINDOW_4H` work | one transaction stores both manifests, exact 4h windows for eligible slots, slot advancement, steps, jobs and campaign work | any fault rolls back the whole fresh plan; complete exact replay is idempotent; partial state fails closed |
| 4h selection/claim | `_select_next_pending_step`, `claim_job`, and exact campaign-work sync | Central Scheduler is the sole claim authority | category first, close-phase order/deadline inside the winning category, then token/cycle fairness | no local worker loop or direct claim bypass found |
| 4h source/execution | `_execute_long_4h_step` reusing governed snapshot/context owners | one claimed Scheduler unit at a time; pre-close forks into one governed source unit per claim with reselection | governed observation, physical snapshot/window, quality path | source/provider/evidence/technical failures remain categorical and token-local unless a shared integrity/budget/stop boundary fires |
| 4h terminal | `_bind_owned_long_memory_window_at_close` -> `reconcile_4h_terminal_lifecycle` | bind/reconcile precedes Scheduler success | campaign window becomes `CLEAN_PROMOTED`, `DIRTY`, `NO_PROMOTION`, or `ALREADY_EXISTS_IDEMPOTENT`; slot becomes `WINDOW_4H_CLOSED`; step/job/work succeed | failed/cancelled work makes exact window `BLOCKED`/`CANCELLED` and slot `FAILED`/`MANUAL_REVIEW` with the same cause |
| campaign observation | factory terminal validation, full-run accounting, unified closure and final report | reads stored steps/jobs/work | exact owned terminal 4h rows can be validated | progression absence and primary barrier-fault truth are incomplete; later accounting can block without restoring the lost cause |

No production path creates `WINDOW_12H` or `WINDOW_24H`. No automatic
successor, campaign restart, resume, or retry was found.

## 2. Eligibility and progression authority

The exact event that currently invokes progression is the committed success of
a `CONTINUATION_CLOSE` or `CONTINUATION_CLOSE_AUDIT` run step. The barrier is
called after its step, Scheduler job, stage-scoped campaign work, exact physical
memory binding, campaign `WINDOW_1H` terminal state, and slot
`WINDOW_1H_CLOSED` have committed.

Barrier release is nevertheless indirect:

1. `_owned_first_hour_state` requires one exact campaign `WINDOW_1H` and one
   exact successful close step for each of the two slots;
2. it checks that the close and campaign window bind the same physical memory;
3. `_continuation_input` reloads physical close, promotion, safety, continuity,
   token/pair/mint/lifecycle and lane facts;
4. token-local hard gates derive the 0/1/2 eligible subset; and
5. the planner's persistence owner finally requires the eligible predecessor
   campaign window to be `CLEAN_PROMOTED`, the slot to be
   `WINDOW_1H_CLOSED`, and exactly one clean physical episode.

There is no dedicated persisted “progression evaluated” or “eligible but plan
not created” state before the planning transaction. The initial barrier reader
also does not require the campaign window's terminal state or the slot's
`WINDOW_1H_CLOSED` state; those facts are enforced later by the planner. This
split can fail closed on drift, but it does not make the barrier event itself a
single durable authority.

Identity coverage is mixed:

- exact: campaign, configuration, campaign run, authoritative factory run,
  cycle, two token slots, slot ordinal, token row, mint, pair row, pair address,
  lifecycle root, predecessor campaign window and physical memory row;
- lane: derived from the successful close step, falling back to physical
  supporting context;
- missing at the barrier: no exact `tracking_queue_id` is selected or compared
  with the lane/current queue row. The later Scheduler work targets campaign
  window identity and retains token/pair/lane, but Scheduler `target_id` is
  deliberately null.

Therefore progression is based on real persisted facts, but not on one
canonical persisted progression record, and the lane is not bound through the
exact tracking-queue identity at this boundary.

## 3. Standard-4H creation, claim, and execution ownership

Fresh creation is atomic. `plan_standard_campaign_4h_handoff` starts a clean
transaction and, for the exact 0/1/2 eligible subset:

- appends a two-slot eligibility manifest to each successful 1h close result;
- creates one exact campaign `WINDOW_4H` per eligible slot;
- advances only eligible slots to `WINDOW_4H_CONTINUING`;
- creates policy-derived `LONG_CONTINUATION_*` run steps and Scheduler jobs;
- projects every job to exact V2 stage-scoped campaign work at `WINDOW_4H`;
- attaches the pre-close campaign owner; and
- verifies the complete plan before commit.

The Standard-4H jobs use `TRACK_FAST_4H`/`TRACK_NORMAL_4H` for ordinary
observations and `MEMORY_WINDOW_CLOSE` for pre-close, evidence, context, and
audit phases. The existing Lane-2 selector remains category-first. Deadline is
considered only inside the winning category, using accepted evidence cutoff
provenance; close dependency order and token/cycle fairness follow. Pre-close
work still executes one governed source unit per claim and reselects after each
unit. No Source Governor or Central Scheduler bypass was found.

The barrier itself is direct coordinator logic, not a Scheduler job. That is
the unowned fault boundary; it does not execute source work, but its failure can
alter already-terminal Scheduler truth.

## 4. Fault-preservation map

| Failure class | Current durable truth | Preservation result |
| --- | --- | --- |
| Provider/source scarcity | source request plus response/failure rows; step IDs/result/error; Scheduler `last_error`; campaign work source IDs/state; exact window/slot terminal cause when collection blocks | generally preserved token-locally; this was not causal in the consumed 4/2/2 run |
| Evidence late/unavailable | Lane-2 source-unit manifest records `LATE`, `DENIED`, `FAILED`, `MISSED_CUTOFF`, `UNKNOWN_INTERRUPTED_AFTER_REQUEST`, or truthful unavailable/degraded context; later E2Q decides clean eligibility | preserved in step/source evidence; honest degraded context is not converted into a technical success claim |
| Honest non-CLEAN memory | physical memory remains dirty/audit/do-not-train or clean-but-unpromoted; successful close step/job/work remains success; campaign window is `DIRTY` or `NO_PROMOTION` | preserved and distinct from technical failure; no dirty clean promotion |
| Technical/integrity failure during claimed 4h work | step `FAILED` with exception/category; Scheduler `FAILED`; campaign work sync; exact window `BLOCKED`; slot `FAILED` | preserved for the normal claimed-work path, token-local, no retry |
| Scheduler failure/cancellation | Scheduler status/`last_error`, work state/cause, step state/error, window/slot terminal state | preserved for normal active work; shared cleanup may use the run-wide stop cause rather than a more specific earlier local cause |
| Operator/external stop | loop stop reason and terminal cleanup; active exact windows cancelled; slots move to manual review | categorical stop survives; it is shared rather than token-specific |
| Timeout/interruption | governed timeout may survive as source failure; pre-close request-without-result is recognized as `UNKNOWN_INTERRUPTED_AFTER_REQUEST`; `KeyboardInterrupt` maps to operator interruption | graceful paths are categorical; abrupt process death leaves active rows and no automatic owner to finalize them |
| Ambiguous/incomplete persisted state | partial 4h plan or partial manifest fails closed; exact plan replay only | ambiguity is detected, but no durable progression-attempt row explains a pre-plan absence |
| Barrier/planning exception after committed 1h success | original exception exists only in the call stack; the handler rewrites the already-successful 1h step/job, attempts later reconciliation, and can emit only generic `SAFE_STOP_PREFLIGHT_FAILED` | **not preserved**; consumed production evidence proves final `fault_details={}` and no recoverable primary exception |

The first-cause violation occurs at the post-commit barrier boundary. The inner
handler is written for a still-running token step, but it also catches the
later barrier. It unconditionally changes the successful step to `FAILED` and
`fail_job(..., max_retries=0)` unconditionally changes the already-successful
Scheduler job to `FAILED`. Subsequent campaign-work/window reconciliation can
then fail because those surfaces were already terminal. That secondary failure
escapes to the outer handler, which stores only the generic preflight stop. A
later generic status can therefore both rewrite terminal success and mask the
original barrier cause.

## 5. Crash/restart map

| Crash point | Persisted state | Classification |
| --- | --- | --- |
| after both 1h terminals, before barrier/4h creation | exact successful 1h rows; no manifest, 4h window, step, job or work | **ambiguous/currently unsafe**: no durable eligible-not-created disposition and no automatic restart |
| during fresh 4h planning | SQLite transaction contains manifests, windows, slots, steps, jobs and work | **resumable only after rollback, operationally unsafe**: commit is all-or-none, but no restart is authorized; a hard process/SQLite outcome must be inspected |
| after plan commit, before claim | full manifest and `PLANNED`/`PENDING` graph | **structurally resumable, not automatically authorized**: normal stop cancels; hard crash leaves active residue for explicit recovery/review |
| during a claimed 4h step | step/job/work `RUNNING`; window `COLLECTING` or `CLOSE_PENDING`; lease/lock may remain | **currently unsafe/interrupted**: explicit recovery is required; no implicit retry/resume |
| after provider request, before terminal persistence | durable request may have no response/failure, or terminal source evidence may exist while step/job remain running | **ambiguous**: pre-close reconciliation can identify request-only interruption, but only if separately authorized to re-enter; ordinary claimed work is not an automatic resume |
| after 4h terminal commit, before campaign accounting/report sync | exact step/job/work/window/slot terminal truth is durable; later report/accounting may be absent/stale | **terminal execution, reporting resumable separately**: report-only reconciliation may use stored facts, but no automatic successor/restart is allowed |

Graceful shared terminalization cancels active owned 1h/4h work and releases
the lease. An abrupt process stop can bypass that `finally` path. The presence
of explicit recovery/report-only tooling does not grant automatic recovery
authority in Lane 3.

## 6. Token and cycle isolation

### Token isolation

Once a 4h plan exists, collection failure is exact-token scoped:
`_cancel_pending_for_token` touches only the token's remaining steps, and
`_terminalize_owned_long_window` requires exact campaign/run/cycle/slot/window/
token/pair identity. The peer remains schedulable, and Lane-2 fairness is
retained.

Before plan creation, isolation is incomplete. `_owned_first_hour_state` raises
if either close is `FAILED`, `CANCELLED`, or otherwise not `SUCCEEDED`. That
shared exception can enter the post-commit rewrite/masking path and stop the
otherwise-valid peer. Honest hard-gate ineligibility after a successful close
does support the correct 0/1/2 subset; actual failed/cancelled first-hour work
does not have an equivalent token-local progression disposition.

### Cycle isolation

All campaign windows and stage-scoped work retain exact campaign run and cycle
identity. In the 4/2/2 controller, `owned_proof_cycle_id` deliberately keeps
the first-hour/4h suffix on Cycle 1 while Cycle 2 supplies the later two 15m
slots. No cross-cycle 4h creation or Cycle-3 creation was found.

Current code assumes exactly two slots per cycle and the 4/2/2 controller
assumes exactly two admitted cycles. A future Cycle-3 authorization would need
an explicit new controller/accounting design; it must not be inferred from the
existing cycle key or enabled in this lane.

## 7. Accounting and reporting findings

The raw persisted graph can distinguish created `PLANNED`/pending, running,
succeeded, failed and cancelled work through campaign windows, run steps,
Scheduler jobs and campaign scheduler work. A complete two-slot eligibility
manifest distinguishes ineligible slots from eligible created slots.

It cannot truthfully distinguish all requested progression states:

- **never eligible:** visible only after a completed manifest says `eligible=false`;
- **eligible but not created:** no durable state;
- **created and pending/running:** directly visible;
- **succeeded/failed/cancelled:** directly visible after normal terminalization;
- **interrupted/ambiguous:** inferred from active/request-only residue, not a
  canonical progression disposition.

`_standard_campaign_four_hour_terminal_validation` returns
`enabled=False, complete=True` when both the manifest and 4h windows are absent. The later
full-run accounting owner instead requires a complete manifest and blocks when
it is absent. These two consumers disagree, and the earlier validator can treat
absence of progression as completion/fallback rather than explicit failure.

The final campaign report exposes stored windows/work and one shared first
terminal cause, but it has no dedicated progression fault envelope. The
consumed run proves its `fault_details` path did not retain the barrier cause.

The known Cycle-2 `NO_CAMPAIGN_SLOT_FOR_TOKEN`,
`SCHEDULER_PROJECTION_WITHOUT_WINDOW`, and N=2 selective-1h reporting
assumptions are baseline multi-cycle accounting/reporting debt assigned to
Lane 4. They did not cause the missing 4h rows and are not reopened here.

## 8. Classification: defects, gaps, and non-code limitations

Each blocker has one primary Python Builder Guide classification.

| Finding | Primary classification | Audit disposition |
| --- | --- | --- |
| post-barrier handler rewrites already-successful step/Scheduler state and can mask the original exception | `COMMITTED_CODE_DEFECT` | `PROVEN_CODE_DEFECT`; design required |
| shared health/lease/integrity/campaign-budget and token-budget/eligibility values are synthesized at the live barrier | `COMMITTED_CODE_DEFECT` | `PROVEN_CODE_DEFECT`; production producers exist but are not consumed here |
| failed/cancelled 1h peer raises shared barrier error instead of a durable token-local progression disposition | `COMMITTED_CODE_DEFECT` | `PROVEN_CODE_DEFECT`; reachable from real step terminal states |
| absent manifest plus absent 4h rows can validate as disabled/complete | `COMMITTED_CODE_DEFECT` | `PROVEN_CODE_DEFECT`; absence can be mistaken for success/fallback |
| no durable pre-plan progression attempt/disposition or eligible-not-created state | `DESIGN_GAP` | exact design input; do not invent a row/status before design |
| no exact tracking-queue identity/queue-state bind at the 1h->4h barrier | `DESIGN_GAP` | exact design input; current lane string alone can drift |
| consumed-run exact first failing 4h exception text | `UNKNOWN_REQUIRES_RESEARCH` | `MISSING_EVIDENCE`; do not guess the historical call or patch a hypothetical cause |
| provider/source scarcity in the consumed run | `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE` | hypothesis rejected: zero causal source failures; no provider/source repair justified |
| honest non-CLEAN, stale, unavailable, safety, continuity, or market/evidence block | `EXPECTED_OPERATIONAL_BLOCKER__NO_CODE_CHANGE` | valid hard-gate result, not a code defect |
| Cycle-2 terminal accounting/reporting projection errors | `DESIGN_GAP` | baseline Lane-4 debt; not runtime-causal and not reopened |
| Cycle 3 | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` | permanently locked in this lane |

No source/provider limitation or missing market evidence explains the proven
post-1h no-4h production outcome. No paid data, budget expansion, weaker
quality rule, or provider change is justified.

## 9. Production-Path Completeness Gate

Result: **FAIL for current runtime completeness; PASS for audit completeness and
separate design readiness.**

- Real producers exist for 1h close, Scheduler terminal state, campaign work,
  physical memory, exact campaign window and slot state.
- Real consumers exist for 4h planning, Scheduler claim, governed collection,
  terminal reconciliation and reporting.
- The progression failure itself has no durable producer/consumer boundary.
- The barrier does not consume real shared health/budget or tracking-queue
  authority even though those production facts exist.
- The consumed run proves the failure state is reachable without test-only
  injection.
- The opposite/safe case is represented by the atomic 0/1/2 plan and exact 4h
  terminal graph, but no production run proves it after the consumed failure.

Passing existing offline tests would not close these production-path gaps. No
new runtime state should be implemented until the separate design names both a
real producer and every required consumer.

## 10. Exact inputs for a separate design lane

These are requirements, not a repair design:

1. Preserve the committed 1h step/job/work/window/slot success as immutable
   predecessor truth when later progression evaluation fails.
2. Define one production-owned, durable, exact-identity progression attempt and
   terminal disposition capable of representing 0/1/2 eligibility, including
   eligible-but-not-created and interrupted/ambiguous outcomes.
3. Bind campaign/configuration/run/factory-run/cycle/slot/token/mint/pair/
   lifecycle/predecessor-memory/tracking-queue/lane identity at one boundary.
4. Consume real campaign state, supervision/lease, DB/integrity, cancellation,
   campaign budget and token budget producers; no synthesized healthy values.
5. Keep successful non-CLEAN memory distinct from provider scarcity, evidence
   lateness, technical/integrity failure, Scheduler cancellation, external stop
   and abrupt interruption.
6. Preserve the first exact safe fault cause through progression, run step,
   Scheduler, campaign work, window/slot, run/cycle/campaign accounting,
   canonical report and terminal summary; later cleanup/report faults must be
   secondary only.
7. Preserve token-local peer continuation for an otherwise-valid slot without
   treating shared integrity/lease/budget failure as token-local.
8. Define crash dispositions at every boundary in the crash map without adding
   automatic retry, resume, restart, rerun, successor or duplicate creation.
9. Make runtime validation and full-run accounting agree that absence is not
   completion when standard progression was required.
10. Preserve Lane-2 category/deadline/fairness, one-unit claim, reselection,
    evidence-time, degraded-context and fail-closed technical-context contracts.
11. Prove no `WINDOW_12H`/`WINDOW_24H`, Cycle 3, retrieval or financial surface
    is created or unlocked.

The design must not assume the lost consumed-run exception. It must first cover
the independently proven production boundaries above and specify how a future
focused proof injects underlying failures rather than expected classifications.

## 11. Explicitly unchanged / forbidden

Do not change or reopen:

- Lane-2 category-first ordering, within-category evidence deadlines,
  token/cycle fairness, last-ACTUAL-capture provenance, pre-close fork/join,
  one governed source unit per claim, reselection after each unit, accepted
  evidence-time rules, degraded-context success, or technical-context fail
  closed behavior;
- Source Governor or Central Scheduler ownership;
- clean/dirty/do-not-train rules or the standard hard gates;
- 5m support-only semantics;
- the 4/2/2 authorization, which is permanently consumed;
- automatic retry, rerun, resume, restart or successor behavior;
- Cycle 3, 12h/24h, retrieval, BUY/SELL/HOLD, positions, trade events, paper
  audits, PnL, wallets/private keys/signing/real execution, paid APIs,
  scoring/ranking/confidence/weighted logic, embeddings or vectors; or
- Lane-4 multi-cycle terminal accounting/reporting debt during Lane-3 design.

## 12. Readiness conclusion and next permitted action

The real production path is sufficiently established to design a bounded
Lane-3 repair. The runtime itself is not ready for Cycle 3, another campaign,
or any activation.

Exact next permitted action:

```text
LANE 3:
Post-1H Standard-4H Progression + Fault Preservation
DESIGN / SPECIFICATION ONLY.
```

Do not implement the design in the audit run. Do not activate Cycle 3.

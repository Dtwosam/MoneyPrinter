# Printer V1 V2-9.8B Post-DTW100 WINDOW_1H Checkpoint 2 — Continuation Initialization Audit

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_2_AUDIT_BLOCKED_WINDOW_LIFECYCLE_SCHEDULER_OWNERSHIP_LINK_REQUIRED`

Checkpoint 2 starts only after Checkpoint 1 has successfully created the exact `WINDOW_1H` successor ownership row and advanced the continuing token slot to `WINDOW_1H_CONTINUING`.

The existing shared lifecycle-continuity, cadence, factory-run-step, Central Scheduler, and Source Governor machinery already provides the correct remaining-45-minute first-hour plan. The blocking gap is narrower: continuation Scheduler jobs are created from the factory's exact current-run 15m close, but the scheduling path does not bind those jobs to the exact `WINDOW_1H` campaign window created by Checkpoint 1.

The schema and canonical ownership helper required to make that binding already exist. This checkpoint should reuse them rather than create any new Scheduler or ownership subsystem.

## Baseline

- Repository: `Dtwosam/MoneyPrinter`
- Checkpoint-1 closeout / exact starting HEAD: `9e0fce811b6f1ea521fb4e4baad2b8289db01fe4`
- Checkpoint-2 branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint2-continuation-initialization`
- Branch created exactly from Checkpoint-1 closeout HEAD.

No source fetching, Scheduler runtime, authoritative DB mutation, authorization creation, wrapper execution, live memory collection, retrieval, paper decision, position, trade, audit, PnL, wallet, signing, or real-fund action occurred in this audit.

## Healthy and reusable continuation machinery

### Exact continuous clock

`lifecycle_continuity.build_1h_continuation_plan()` uses the current-run 15m close as the continuation anchor. It defines:

- enqueue immediately at the exact 15m close;
- deadline = exact 15m close + 2700 seconds;
- no delayed-first-snapshot clock reset;
- exact linkage to the 15m memory-window row and 15m closing snapshot.

The authoritative cadence contract defines `WINDOW_1H` as the remaining `t=15m..60m` phase, not another 60-minute window.

### Correct 1h cadence

The shared cadence owner already defines:

- `TRACK_FAST`: 120-second nominal cadence, 24 expected continuation snapshots;
- `TRACK_NORMAL`: 240-second nominal cadence, 13 expected continuation snapshots;
- continuation duration: 2700 seconds;
- 15m→1h transition thresholds:
  - FAST: expected <=120s, dirty >180s, block >240s;
  - NORMAL: expected <=240s, dirty >360s, block >480s.

`WINDOW_1H` is enabled for real collection; longer windows remain locked.

### Existing Central Scheduler reuse

`one_command_15m_factory._plan_continuation_jobs()` does not create a private timer or loop. It uses the existing `_insert_step_and_job()` owner, which maps:

- `CONTINUATION_SNAPSHOT` -> `TRACK_FAST_1H` / `TRACK_NORMAL_1H` Central Scheduler job kinds;
- `CONTINUATION_CLOSE` -> the existing `MEMORY_WINDOW_CLOSE` Scheduler kind.

The first continuation snapshot is scheduled at offset zero from the exact 15m close. The final close is scheduled at close + 2700 seconds.

### Existing Source Governor reuse

When a continuation snapshot executes later, it uses the same governed exact-pair snapshot path as 15m. Source requests are constructed and executed through Source Governor. No new source adapter or source loop is required by Checkpoint 2.

### Existing campaign Scheduler ownership authority

Migration 050 and `campaign_ownership.project_campaign_scheduler_job()` already provide the exact `WINDOW_LIFECYCLE` ownership contract. That authority verifies:

- exact campaign/run/cycle;
- exact token slot;
- exact campaign window;
- exact factory run;
- exact Scheduler job;
- exact factory run-step linkage;
- target identity equals the campaign window;
- one Scheduler job has only one campaign ownership row.

This is the owner Checkpoint 2 should reuse.

## Blocking integration gap

The current standard-first-hour barrier performs these operations in order:

1. create/reconcile exact 15m campaign-window ownership;
2. evaluate the standard first-hour policy;
3. Checkpoint 1 atomically creates the immutable continuation set, exact `WINDOW_1H` successor row, and `WINDOW_1H_CONTINUING` token state;
4. `_selective_1h_schedule_for_close()` decides whether this exact token continues;
5. `_resolve_current_run_15m_source()` resolves the current-run 15m memory source;
6. `_plan_continuation_jobs()` creates factory run-steps and Scheduler jobs for the remaining 45 minutes.

At step 6, `_plan_continuation_jobs()` receives no campaign/run/cycle/token-slot/`campaign_window_1h_id` ownership context. `_insert_step_and_job()` returns the exact Scheduler job id and persists the exact factory run-step, but no `WINDOW_LIFECYCLE` projection is created for the new 1h jobs.

Therefore the current DB can contain:

- a valid `CONTINUE_TO_WINDOW_1H` immutable decision;
- the exact `WINDOW_1H` campaign window;
- token state `WINDOW_1H_CONTINUING`;
- valid continuation factory run-steps and Scheduler jobs;
- **zero exact campaign Scheduler ownership rows linking those jobs to that `WINDOW_1H` window**.

That breaks the campaign ownership chain precisely at continuation initialization.

## Why this is a blocker

The current campaign Scheduler schema explicitly requires `WINDOW_LIFECYCLE` work to carry exact factory-run, token-slot, and window linkage. The existing projection helper was built to prevent Scheduler jobs from being inferred post hoc from generic run-step existence.

A first-hour continuation whose jobs are not owned by its exact campaign window weakens:

- cancellation and cleanup attribution;
- terminal reconciliation;
- exact window-to-job accounting;
- later full composition proof;
- proof that the 1h evidence belongs to the same governed lifecycle as its 15m predecessor.

It would be unsafe to move into Checkpoint 3 collection while this ownership link is absent.

## Required repair direction

Reuse `campaign_ownership.project_campaign_scheduler_job()` immediately after each continuation Scheduler job/run-step is created.

The scheduling path must receive the exact Checkpoint-1 token plan and use:

- `campaign_id`;
- campaign `run_id`;
- `cycle_id`;
- `token_slot_id`;
- exact `campaign_window_1h_id`;
- factory `run_id`;
- exact returned `scheduler_job_id`;
- deterministic Scheduler-work identity;
- exact scheduled deadline/work intent.

Every `CONTINUATION_SNAPSHOT` and the one `CONTINUATION_CLOSE` must project as `V2_STAGE_SCOPED / WINDOW_LIFECYCLE / CAMPAIGN_WINDOW` against the exact `WINDOW_1H` successor.

Projection failure must fail the continuation initialization; it may not be swallowed or reconstructed later.

## Minimum focused proof

The repair must prove, offline:

1. successful two-token Checkpoint-1 handoff creates two exact `WINDOW_1H` successors;
2. 45-minute scheduling creates the cadence-derived continuation jobs at the exact 15m-close anchor;
3. every created continuation Scheduler job has exactly one `V2_STAGE_SCOPED` `WINDOW_LIFECYCLE` ownership row;
4. every ownership row points to the correct token slot, exact `WINDOW_1H` successor, campaign run, cycle, and factory run;
5. each projected job is backed by the exact factory run-step;
6. first continuation snapshot is scheduled at the 15m close; final close is exactly +2700s;
7. FAST/NORMAL expected counts stay aligned with cadence policy;
8. a wrong/missing `campaign_window_1h_id`, token slot, campaign run, factory run, or Scheduler job fails closed;
9. repeated evaluation/scheduling cannot create duplicate owned jobs;
10. existing Checkpoint-1 and first-hour operational suites remain green.

## Money-usefulness contribution

A first-hour memory is useful only if its observations are provably part of the same governed lifecycle as the clean 15m predecessor. Exact campaign-window Scheduler ownership makes every 1h observation attributable and prevents orphan or cross-window Scheduler work from contaminating trajectory memory.

## What this checkpoint improves

When repaired, Checkpoint 2 will establish the trustworthy initialization boundary:

`clean 15m -> exact 1h successor ownership -> exact 2700s schedule -> exact Scheduler jobs -> exact WINDOW_1H campaign ownership`.

## What this checkpoint still does not unlock

- no real 45-minute continuation run;
- no provider/RPC calls;
- no authoritative DB mutation;
- no one-use authorization/wrapper;
- no proof yet that all remaining 45-minute jobs execute correctly — Checkpoint 3;
- no proof yet of 1h close quality — Checkpoints 4-6;
- no 4h activation;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- Do not build a second Scheduler ownership table/helper; migration 050 and the canonical projection already exist.
- Do not project jobs before their factory run-step exists because the canonical validator intentionally requires exact run-step linkage.
- Do not derive ownership later from step-key naming; bind at creation time.
- Do not alter cadence or source execution as part of this ownership repair.
- Do not broaden the repair into discovery/15m ownership work already proven by DTW100.

## Next action

Design the narrow continuation Scheduler-to-`WINDOW_1H` ownership wiring repair. Checkpoint 3 remains blocked until implementation, focused proof, and Checkpoint-2 closeout pass.

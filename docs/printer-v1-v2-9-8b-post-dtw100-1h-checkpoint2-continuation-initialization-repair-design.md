# Printer V1 V2-9.8B Post-DTW100 WINDOW_1H Checkpoint 2 — Continuation Scheduler Ownership Repair Design

## Design verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_2_WINDOW_LIFECYCLE_SCHEDULER_OWNERSHIP_REPAIR_DESIGN_PASS`

This design wires the already-proven 45-minute continuation Scheduler jobs to the exact Checkpoint-1 `WINDOW_1H` campaign successor. It changes no cadence, continuation eligibility, source execution, memory-quality, or financial behavior.

## Canonical owners

Reuse only:

- scheduling/orchestration: `src/printer_v1/operator_cli/one_command_15m_factory.py`;
- campaign Scheduler ownership: `src/printer_v1/operator_cli/campaign_ownership.py::project_campaign_scheduler_job`;
- lifecycle clock: `src/printer_v1/snapshots/lifecycle_continuity.py`;
- cadence: `src/printer_v1/snapshots/cadence_policy.py`;
- Central Scheduler: existing `_insert_step_and_job()` / Scheduler owner;
- Source Governor: existing governed snapshot execution boundary.

No new scheduler, loop, ownership table, migration, source adapter, or memory owner is allowed.

## Required wiring

### 1. Carry exact Checkpoint-1 successor context

`_selective_1h_schedule_for_close()` must resolve the exact token plan from the already-persisted standard-first-hour evaluation and require:

- `token_slot_id`;
- `campaign_window_1h_id`;
- `CONTINUE_TO_WINDOW_1H` verdict;
- exact token row matching the close step.

A continuing token without an exact 1h campaign-window id fails closed before any continuation Scheduler job is created.

### 2. Pass one immutable ownership context into continuation planning

The context must contain:

- campaign id;
- campaign run id;
- cycle id;
- token-slot id;
- exact `campaign_window_1h_id`;
- factory run id.

`_plan_continuation_jobs()` may accept this context only for the standard-first-hour operational path. Historical/non-campaign helper callers may continue to omit it where they are explicitly fixture-only, but the repaired V2-9.8B operational barrier must require it.

### 3. Project each job immediately after run-step creation

`_insert_step_and_job()` already returns the exact Scheduler job id after it has inserted the exact factory run-step. `_plan_continuation_jobs()` must use that returned id and call `project_campaign_scheduler_job()` before proceeding to the next continuation job.

For every `CONTINUATION_SNAPSHOT` and `CONTINUATION_CLOSE`:

- `work_scope = WINDOW_LIFECYCLE` through the compatibility wrapper;
- `target_category = CAMPAIGN_WINDOW`;
- `target_identity = exact campaign_window_1h_id`;
- `window_id = exact campaign_window_1h_id`;
- exact token slot;
- exact campaign/run/cycle;
- exact factory run;
- exact Scheduler job id;
- `work_intent` identifies the continuation step kind;
- `deadline_at` equals that job's actual `scheduled_for` value;
- `stage_id` deterministically identifies `WINDOW_1H` lifecycle work;
- deterministic `scheduler_work_id` includes enough immutable identity to prevent collision across jobs/windows.

Projection failure propagates and fails continuation initialization. It must not be swallowed.

### 4. Preserve exact timing

Do not change the current timing algorithm:

- source anchor = current-run closed 15m window;
- first continuation snapshot offset = 0 seconds;
- final continuation close = +2700 seconds;
- FAST expected snapshots = 24;
- NORMAL expected snapshots = 13;
- no new 60-minute clock.

The repair may add a fail-closed assertion that the operational continuation duration equals the authoritative `WINDOW_1H` policy duration (2700 seconds), but it must not invent another timing constant.

### 5. Preserve replay/no-duplicate behavior

The existing campaign barrier schedules only when `evaluation_created` is true. A repeated barrier call must not create additional Scheduler jobs or ownership rows.

The campaign Scheduler ownership table's unique Scheduler-job rule remains authoritative.

## TDD RED contract

Add a checkpoint-specific offline test that drives the real first-hour campaign barrier far enough to create continuation Scheduler jobs and asserts:

1. exact `WINDOW_1H` successor(s) exist from Checkpoint 1;
2. continuation run-steps/Scheduler jobs are created at the correct times;
3. every continuation Scheduler job has exactly one `V2_STAGE_SCOPED / WINDOW_LIFECYCLE` ownership row bound to the exact 1h campaign window.

The current implementation should fail because it creates zero such ownership projections.

Also prove a mismatched or missing exact `campaign_window_1h_id` fails before continuation jobs are created.

## GREEN proof

Minimum sufficient offline verification:

- checkpoint-specific continuation initialization tests;
- Checkpoint-1 handoff tests;
- current standard-first-hour alignment tests;
- current operational first-hour harness;
- directly affected migration-050 Scheduler-ownership tests if the projection contract itself is touched (it should not need modification);
- compilation and diff checks.

No broad repository suite is required unless directly related evidence fails.

## Money-usefulness contribution

Every snapshot used to form a future 1h memory will have a durable, exact ownership path back to the same campaign window and token lifecycle. This removes ambiguity about whether a Scheduler observation belongs to the 15m predecessor, 1h continuation, another token, or another run.

## What this repair improves

- exact 1h Scheduler attribution at creation time;
- one campaign-window owner per continuation job;
- exact factory-run-step ↔ Scheduler-job ↔ campaign-window composition;
- safer cancellation/cleanup and later terminal reconciliation;
- reuses the existing proven Scheduler ownership architecture.

## What remains locked

- no real continuation execution;
- no provider/RPC calls;
- no authoritative DB mutation;
- no one-use authorization/wrapper;
- no Checkpoint-3 collection proof yet;
- no 4h activation;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- Projecting before the run-step exists would violate the canonical ownership validator; projection must occur immediately after `_insert_step_and_job()` returns.
- A loose target based on token id or step-key naming is insufficient; exact `campaign_window_1h_id` is mandatory.
- A new ownership helper would duplicate existing authority and is prohibited.
- The repair must not widen Scheduler or source budgets.
- Timing changes are out of scope unless a focused assertion exposes actual drift.

## Stop condition

Checkpoint 2 closes only when the exact implementation head proves all continuation jobs are correctly timed and exactly owned by the Checkpoint-1 `WINDOW_1H` successor, with the existing first-hour suites still green.

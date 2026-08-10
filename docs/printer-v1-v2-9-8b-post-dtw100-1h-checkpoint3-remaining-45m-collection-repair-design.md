# Printer V1 V2-9.8B Post-DTW100 WINDOW_1H Checkpoint 3 — Active Collection State / Accounting Repair Design

## Design verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_3_ACTIVE_COLLECTION_STATE_ACCOUNTING_REPAIR_DESIGN_PASS`

This repair preserves the existing continuation collection engine. It synchronizes existing campaign ownership and six-unit accounting around that engine; it does not create a new 1h collector, Scheduler, source path, schema, or migration.

## Canonical owners reused

- collection runtime: `one_command_15m_factory.py`;
- Scheduler truth: `printer_scheduler_jobs` + existing scheduler helpers;
- campaign Scheduler projection: `campaign_ownership.project_campaign_scheduler_job()`;
- campaign window state: `campaign_ownership.transition_state()`;
- exact-pair source execution: existing `_execute_snapshot()`;
- Source Governor: existing governed execution boundary;
- lifecycle request projection: existing `_projected_requests_for_step()`;
- lifecycle reservation observer: existing `LIFECYCLE_RESERVATION` record shape.

## Repair 1 — exact owned Scheduler state sync

Add a private factory helper, conceptually `_sync_owned_campaign_scheduler_job(conn, job_id)`.

Behavior:

1. find the exact row in `printer_memory_factory_campaign_scheduler_work` by `scheduler_job_id`;
2. zero rows -> return `None` for historical/non-campaign compatibility;
3. more than one row -> fail closed (schema should already prevent this);
4. call `project_campaign_scheduler_job()` with the stored immutable stage/window/campaign/factory identities and exact job id;
5. the canonical owner revalidates the backing run-step and derives current Scheduler state;
6. return the resulting/current work state.

Invoke after:

- successful `claim_due_job()` and run-step `RUNNING` transition;
- `complete_job()`;
- `fail_job()`;
- every `cancel_job()` in `_cancel_pending()` and `_cancel_pending_for_token()`.

Do not synthesize Scheduler state from the run-step.

## Repair 2 — exact WINDOW_1H active-state sync

Add a private helper that resolves an owned continuation job's exact `WINDOW_1H` campaign window through the campaign Scheduler ownership row.

For `CONTINUATION_SNAPSHOT` only:

- on first successful claim, require the exact owned window;
- if window state is `PLANNED`, call the canonical `transition_state()` for `PLANNED -> COLLECTING`;
- if already `COLLECTING`, leave unchanged;
- any other nonterminal/terminal state is a fail-closed conflict for collection execution.

On a token-local continuation collection failure:

- synchronize the failed Scheduler work row;
- cancel remaining pending jobs for that token and synchronize their ownership rows;
- terminalize that token's exact active `WINDOW_1H` campaign window as `BLOCKED`, preserving a durable terminal cause;
- do not alter the peer token/window.

On global/operator cancellation:

- after pending job cancellation, terminalize any nonterminal exact `WINDOW_1H` campaign windows with outstanding owned work as `CANCELLED`;
- do not relabel them CLEAN/DIRTY.

Do not transition to `CLOSE_PENDING` here. Checkpoint 4 owns the close boundary.

## Repair 3 — continuation lifecycle reservation records

Replace the narrow observer condition:

`SNAPSHOT | WINDOW_CLOSE`

with the exact lifecycle source-consuming set:

- `SNAPSHOT`
- `WINDOW_CLOSE`
- `CONTINUATION_SNAPSHOT`
- `CONTINUATION_CLOSE`

Use `_projected_requests_for_step()` unchanged. Therefore:

- ordinary snapshot = 1 reservation;
- 15m close = existing close reservation bundle;
- continuation snapshot = 1 reservation;
- continuation close = 1 reservation.

Operation-family labels:

- `CONTINUATION_SNAPSHOT` -> `CONTINUATION_SNAPSHOT_OBSERVATION`;
- `CONTINUATION_CLOSE` -> `CONTINUATION_CLOSE_OBSERVATION`.

No budget ceiling or provider call count changes.

## Atomicity / ordering

For an owned continuation step:

1. Scheduler claim succeeds;
2. factory step becomes `RUNNING`;
3. campaign Scheduler work synchronizes to `RUNNING`;
4. first continuation snapshot marks exact 1h window `COLLECTING`;
5. budget/reservation validation occurs;
6. governed exact-pair source executes;
7. snapshot persists on success;
8. factory step becomes terminal;
9. Scheduler job becomes terminal;
10. campaign Scheduler work synchronizes to the Scheduler terminal state;
11. commit.

A synchronization fault is an integrity fault and must not be swallowed.

## TDD RED contract

Add a Checkpoint-3 focused test module using a disposable migrated DB and the existing Checkpoint-2 fixture/owners.

Prove current RED for at least:

1. after a real CP2 initialization, manually claim the first owned continuation job and show campaign work remains `PENDING` before repair;
2. exact `WINDOW_1H` remains `PLANNED` after collection has begun before repair;
3. continuation lifecycle reservation helper/observer currently emits zero reservation identities for a `CONTINUATION_SNAPSHOT`.

The test may exercise `_execute_snapshot()` with fixture source adapters to prove existing source/snapshot behavior without waiting 45 real minutes.

## GREEN proof

Minimum sufficient proof:

- new Checkpoint-3 state/accounting tests;
- Checkpoint-2 initialization tests;
- Checkpoint-1 handoff tests;
- current standard-first-hour alignment tests;
- current operational first-hour harness;
- directly affected Scheduler ownership tests;
- compile + diff checks.

Also prove token-local failure isolation and cancellation synchronization with disposable data. No live source proof in this checkpoint.

## Money-usefulness contribution

Printer gains a truthful active first-hour chain: every observation, Scheduler state, campaign-work state, and main-window state agrees about what was actually happening. That makes later 1h trajectory memory auditable and prevents orphan/stale ownership from being mistaken for completed evidence.

## What improves

- PENDING/RUNNING/terminal Scheduler ownership truth;
- `WINDOW_1H` becomes COLLECTING when collection actually begins;
- blocked/cancelled collection leaves a terminal campaign-window fact;
- continuation source capacity is represented by existing lifecycle reservation accounting;
- same 15m source/snapshot/Scheduler owners remain in use.

## What remains locked

Real first-hour execution, authorization/wrapper, 1h close audit, clean 1h memory closeout, 4h activation, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, signing, real funds, paid APIs, scoring/ranking/confidence/weighting, embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Synchronization must follow Scheduler truth, never create a competing state machine.
- Cancellation must remain token-local unless a shared/global stop occurs.
- Campaign-window active-state changes must not imply memory quality.
- Reservation reporting must not change capacity.
- Existing historical fixture-only continuation callers may have no campaign ownership rows; sync helper must no-op only in that explicit zero-row case.

## Stop condition

Checkpoint 3 closes only when the exact implementation head proves the remaining-45m collection path has truthful job/window/accounting state and the existing first-hour suites remain green. Checkpoint 4 does not begin before that PASS.

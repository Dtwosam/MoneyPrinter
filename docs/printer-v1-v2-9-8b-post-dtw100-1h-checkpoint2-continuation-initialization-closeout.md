# Printer V1 V2-9.8B Post-DTW100 WINDOW_1H Checkpoint 2 — Continuation Initialization Closeout

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_2_CONTINUATION_INITIALIZATION_PASS`

Checkpoint 2 is complete. Starting from the exact `WINDOW_1H` successor and `WINDOW_1H_CONTINUING` token state proven by Checkpoint 1, Printer now initializes the remaining 45-minute first-hour schedule from the exact current-run 15m close and durably binds every created continuation Scheduler job to that exact `WINDOW_1H` campaign window through the existing stage-scoped campaign Scheduler ownership authority.

The repair reuses the existing lifecycle-continuity planner, cadence policy, Central Scheduler, factory run-step ledger, migration-050 ownership schema, and `project_campaign_scheduler_job()` owner. It creates no parallel Scheduler, source loop, ownership subsystem, migration, or memory engine.

## Baseline and commits

- Checkpoint-2 starting / Checkpoint-1 closeout HEAD: `9e0fce811b6f1ea521fb4e4baad2b8289db01fe4`
- Audit commit: `75b39e84a7cec8ca615b517c25fbee83a78ca99f`
- Repair design commit: `5598ba28773811a534afb801401d7a96f918f68d`
- Initial Checkpoint-2 test commit: `33db786bf7602509d6494a6d442a035ac60c4757`
- Real-close-ledger fixture correction / valid RED HEAD: `e2aaa13b761cc797a274949659666bdc74506b90`
- Proven implementation HEAD before closeout: `1663932ed6abf223d16af4a27937f3058c5d7a06`
- Branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint2-continuation-initialization`

## Healthy reusable machinery confirmed

The audit confirmed that no new 1h timing engine was needed.

The existing shared owners already provide:

- exact current-run 15m closing-memory and closing-snapshot authority;
- first-hour continuation anchor at that exact 15m close;
- continuation duration of exactly 2700 seconds (`t=15m..60m`), not a fresh 60-minute clock;
- `TRACK_FAST` 120-second cadence with 24 expected continuation jobs including close accounting;
- `TRACK_NORMAL` 240-second cadence with 13 expected continuation jobs including close accounting;
- first continuation snapshot at the exact 15m-close anchor;
- final continuation close at +2700 seconds;
- Central Scheduler job kinds `TRACK_FAST_1H` / `TRACK_NORMAL_1H` and existing memory-window close ownership;
- later snapshot execution through the same governed exact-pair Source Governor path used by the proven 15m machinery.

## Blocker found

Before this repair, the standard-first-hour barrier correctly created:

- immutable `CONTINUE_TO_WINDOW_1H` decisions;
- exact Checkpoint-1 `WINDOW_1H` successor rows;
- token state `WINDOW_1H_CONTINUING`;
- continuation factory run-steps;
- continuation Central Scheduler jobs.

However, `_selective_1h_schedule_for_close()` / `_plan_continuation_jobs()` did not carry the exact `campaign_window_1h_id` into scheduling and did not project those Scheduler jobs into `printer_memory_factory_campaign_scheduler_work` as `WINDOW_LIFECYCLE` ownership.

Thus valid continuation jobs could exist without durable exact campaign-window ownership.

## Repair implemented

Only the current shared factory Scheduler owner changed:

`src/printer_v1/operator_cli/one_command_15m_factory.py`

### Exact successor preflight

Before any support capture or continuation scheduling for a continuing token, `_selective_1h_schedule_for_close()` now requires and validates:

- exact campaign id;
- exact campaign run id;
- exact cycle id;
- exact token-slot id;
- exact Checkpoint-1 `campaign_window_1h_id`;
- exact predecessor 15m campaign-window id;
- exact token row and pair row;
- `WINDOW_1H` kind;
- `PLANNED` successor-window state;
- no premature memory-window binding;
- token slot already at `WINDOW_1H_CONTINUING`.

Missing or mismatched exact successor authority fails before continuation Scheduler jobs are created.

### Existing Scheduler ownership reused

`_plan_continuation_jobs()` accepts an optional ownership context. The operational V2-9.8B standard-first-hour path supplies it; historical fixture-only callers may omit it.

Immediately after each existing `_insert_step_and_job()` call creates the exact Scheduler job and exact factory run-step, the continuation planner calls the existing `campaign_ownership.project_campaign_scheduler_job()` authority with:

- `ownership_contract_version = V2_STAGE_SCOPED` through the canonical helper;
- `work_scope = WINDOW_LIFECYCLE`;
- `stage_id = WINDOW_1H`;
- `target_category = CAMPAIGN_WINDOW`;
- exact `target_identity = window_id = campaign_window_1h_id`;
- exact campaign/run/cycle;
- exact token slot;
- exact factory run;
- exact Scheduler job id;
- exact scheduled time as `deadline_at`;
- step-kind-specific first-hour work intent.

The projection owner itself was not changed. Its existing validation continues to require the exact campaign window, token slot, authoritative factory run, Scheduler job, and backing factory run-step, and rejects competing ownership.

Projection failure propagates rather than being swallowed.

## Timing contract preserved

No cadence or clock code changed.

For each `TRACK_NORMAL` token in the focused composition proof:

- exactly 13 continuation jobs were created;
- the first job was `CONTINUATION_SNAPSHOT` at the exact 15m close;
- the last job was `CONTINUATION_CLOSE` exactly 2700 seconds later.

For two normal-lane tokens this produced exactly 26 continuation jobs and exactly 26 matching `WINDOW_LIFECYCLE` campaign ownership rows.

FAST/NORMAL cadence remains derived from the authoritative shared cadence policy.

## TDD evidence

### Rejected first RED attempt

The first Checkpoint-2 RED attempt reached `missing_current_run_15m_closing_snapshot` because the older reusable test fixture did not attach its already-existing closing snapshot id to the successful `WINDOW_CLOSE` run-step. Real DTW100-style close ownership does carry that exact linkage.

That run was rejected as target RED evidence. Production code was not changed in response.

The Checkpoint-2 fixture was corrected only to attach its existing closing snapshots (`5001`, `5002`) to the matching current-run close steps.

### Valid RED

- Exact head: `e2aaa13b761cc797a274949659666bdc74506b90`
- Workflow run: `31345787618`
- Job: `93327345181`
- Compilation: PASS
- Tests: 40 total; 38 PASS; exactly 2 intended failures.

The two intended failures were:

1. real two-token barrier created 26 continuation jobs but zero `V2_STAGE_SCOPED / WINDOW_LIFECYCLE` ownership rows (`0 != 26`);
2. deleting the exact `campaign_window_1h_id` from a continuing token plan did not raise and therefore did not fail closed before continuation scheduling.

All Checkpoint-1 and existing operational first-hour tests passed in that RED run.

### Final GREEN

- Exact implementation head: `1663932ed6abf223d16af4a27937f3058c5d7a06`
- Workflow run: `31346129100`
- Job: `93328307749`
- Compilation: PASS
- Result: `Ran 40 tests in 46.278s — OK`
- Total: 40/40 PASS, 0 failures, 0 errors.

The GREEN suite contains:

- 2 Checkpoint-2 continuation-initialization tests;
- 2 Checkpoint-1 strict-handoff tests;
- 4 standard-first-hour clean-object/reporting alignment tests;
- all 32 current operational first-hour tests.

The independent first-hour lifecycle focused workflow also passed on exact implementation head `1663932...`.

## Scope verification

From Checkpoint-1 closeout `9e0fce8...` through proven Checkpoint-2 implementation `1663932...`, the durable branch changes only:

- Checkpoint-2 audit document;
- Checkpoint-2 repair design document;
- `src/printer_v1/operator_cli/one_command_15m_factory.py`;
- `tests/test_v2_9_8b_post_dtw100_checkpoint2_continuation_initialization.py`.

The production implementation change is one existing shared factory/Scheduler owner only. No migration or campaign-ownership implementation changed.

Disposable runner workflows/scripts exist only on disposable proof branches and are not part of this durable branch.

## Money-usefulness contribution

Every scheduled observation intended to form a future 1h memory now has durable exact ownership back to the same `WINDOW_1H` successor, token slot, campaign, factory run, and clean 15m predecessor lifecycle. This prevents orphan or cross-window Scheduler observations from contaminating trajectory learning or memory attribution.

## What this checkpoint improves

- trustworthy 45-minute continuation initialization;
- exact no-reset 15m→1h clock;
- exact Scheduler-job ↔ factory-step ↔ campaign-window linkage;
- exact two-token first-hour ownership;
- fail-closed missing/mismatched 1h successor handling;
- reuse of proven 15m/shared Scheduler and Source Governor machinery.

## What this checkpoint still does not unlock

- no real 45-minute continuation execution;
- no provider/RPC/source fetching;
- no authoritative DB mutation outside disposable offline proof databases;
- no one-use first-hour authorization or wrapper;
- no proof yet that the remaining 45-minute jobs execute and persist evidence correctly — Checkpoint 3 owns that;
- no proof yet of 1h close quality or clean 1h memory completion — later checkpoints own those;
- no 4h activation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trades, paper audits, or PnL;
- no wallet, key, signing, real funds, live execution, paid APIs, scoring/ranking/confidence/weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Scheduler ownership is now established at creation, but Checkpoint 3 must verify ownership remains truthful as jobs move through claim/execute/complete/fail/cancel states.
- The focused proof uses disposable SQLite fixtures; no live source request was made.
- Historical helper callers can still call `_plan_continuation_jobs()` without campaign ownership context; the operational V2-9.8B barrier supplies it. A future generalization must not silently treat fixture compatibility as operational permission.
- No attempt was made to refactor historical `selective_1h` naming; that would be unrelated scope.

## Next checkpoint

`Checkpoint 3 — remaining 45-minute WINDOW_1H collection path`

Audit the current execution path for the now-exactly-owned continuation Scheduler jobs: claim, exact-pair governed source request, snapshot persistence, job/run-step completion, fairness across two tokens, source/Scheduler accounting, token-local versus shared failure behavior, cadence/gap evidence, and ownership-state synchronization. Reuse the proven 15m source/Scheduler/snapshot owners wherever their contracts already apply.

If Checkpoint 3 finds a blocker, stop there and complete audit → repair design → implementation → focused proof → closeout before advancing to the 1h close boundary.

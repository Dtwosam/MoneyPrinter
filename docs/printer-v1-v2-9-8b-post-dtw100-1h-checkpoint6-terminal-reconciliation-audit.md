# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 6 Terminal-Reconciliation Audit

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_6_TERMINAL_RECONCILIATION_AUDIT_BLOCKED_WINDOW_AND_TOKEN_STATE_RECONCILIATION_REQUIRED`

The first-hour collection, close boundary, genuine memory construction, Scheduler terminalization, and campaign Scheduler-work projection are now present. The remaining Checkpoint-6 blocker is lifecycle truth: a successful or failed/cancelled first-hour path can finish its real work while the campaign window and/or owning token slot remain in nonterminal first-hour states.

A bounded design/implementation/proof repair is required before first-hour operational rereadiness can be considered.

## Baseline and scope

- Baseline: `e659d9354ce13b1930fd6c1ea5ee3c3877198cac` — Checkpoint-5 exact-closeout PASS.
- Branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint6-terminal-reconciliation`.
- Scope: exact `WINDOW_1H` campaign-window state, exact owning token-slot state, Scheduler/campaign-work terminal parity, token-local failure isolation, run-wide cancellation reconciliation, and idempotency.

No source fetching, live Scheduler/runtime execution, authorization creation, authoritative DB mutation, operational memory generation, 4h activation, retrieval, paper decision, position, trade, audit, PnL, wallet, signing, or execution occurred.

## Current healthy owners

### Physical first-hour close and memory construction are complete

Checkpoint 4 and Checkpoint 5 already establish:

- the close job claim moves the exact campaign `WINDOW_1H` to `CLOSE_PENDING`;
- the genuine physical `WINDOW_1H` row is created only after valid closing evidence reaches the fixed first-hour deadline;
- the physical row is bound to its exact campaign window;
- the full-first-hour outcome is derived from exact current-run main-lifecycle evidence;
- E2Q, Lane Q/U2, explicit Lane K, and E2Z compose the genuine first-hour memory;
- clean promotion creates one exact `WINDOW_1H_CLEAN_MEMORY` episode plus one canonical fingerprint.

Checkpoint 6 must not reopen those owners.

### Scheduler terminalization is already wired

On a successful `CONTINUATION_CLOSE`, the factory:

1. marks the run step `SUCCEEDED`;
2. binds the exact first-hour physical memory row to the campaign window;
3. calls `complete_job()` for the exact Scheduler job;
4. calls `_sync_owned_campaign_scheduler_job()` so the campaign Scheduler-work row mirrors Scheduler truth;
5. observes the Scheduler terminal boundary;
6. commits.

On token-local failure, the exact Scheduler job is failed, campaign Scheduler-work is synchronized, and remaining pending work for that token is cancelled. Run-wide cleanup also cancels remaining pending work and nonterminal owned first-hour windows.

Therefore this checkpoint does not need a new Scheduler owner, job type, retry path, or active-work engine.

## Blocker 1 — successful first-hour window remains CLOSE_PENDING

The successful factory path currently calls `_bind_owned_continuation_memory_window_at_close()` after `_execute_continuation_close()` succeeds. That helper requires the exact owned campaign window to be `CLOSE_PENDING` and binds `memory_window_row_id`, but intentionally stops there.

No later successful path advances that campaign window:

`CLOSE_PENDING -> AUDITING -> CLEAN_PROMOTED | DIRTY | NO_PROMOTION`

Consequently the real Scheduler work can be completely terminal while the durable campaign-window state still says the first-hour close is pending.

This is lifecycle-state drift, not a memory-construction defect.

## Blocker 2 — successful token slot remains WINDOW_1H_CONTINUING

The standard-first-hour handoff atomically creates each approved `WINDOW_1H` successor and advances its exact token slot to `WINDOW_1H_CONTINUING`.

The token-state law already defines the normal success transition:

`WINDOW_1H_CONTINUING -> WINDOW_1H_CLOSED`

The current first-hour success path never performs that transition after the real close and memory result are known. Therefore an otherwise finished token can remain durably marked as still continuing through the first hour.

Checkpoint 6 should close the token at the first-hour boundary only. It must not advance to `WINDOW_4H_CONTINUING`; 4h remains a separate later policy/activation concern.

## Blocker 3 — failure/cancellation terminalizes the window but can leave the token slot active

Current token-local continuation failure correctly calls `_terminalize_owned_continuation_window(..., terminal_state="BLOCKED")`, and run-wide stop cleanup can move active first-hour windows to `CANCELLED`.

Neither path currently reconciles the owning token slot out of `WINDOW_1H_CONTINUING`.

For an actual token-local first-hour execution failure, the existing token-state machine already permits terminal `FAILED`. For run-wide cancellation/interruption, a token slot must also stop advertising active first-hour continuation; the exact terminal/disposition mapping must be specified rather than inferred ad hoc.

The repair must preserve token-local isolation: one token's failed first hour must not alter its peer's window or token-slot state.

## Blocker 4 — first-hour window terminal classification is not yet bound to the actual memory result

The existing 15m campaign-window registration already supplies the conservative classification pattern:

- exact eligible clean episode exists -> `CLEAN_PROMOTED`;
- source memory is dirty / `do_not_train` / non-clean data -> `DIRTY`;
- otherwise -> `NO_PROMOTION`.

The first-hour success path has the same information after Checkpoint 5, but does not use it to terminalize the campaign `WINDOW_1H`.

The first-hour repair should reuse this evidence meaning, not infer terminal state from a raw E2Z string alone. A clean episode is authoritative clean-promotion evidence; dirty source quality is dirty; an otherwise valid close that produces no clean object is `NO_PROMOTION`. Runtime/source/continuity failure remains `BLOCKED`, not `NO_PROMOTION`.

## Existing reusable state owner

`operational_selective_1h.bind_1h_memory_window()` already owns exact first-hour memory-row binding plus window-state progression through:

`PLANNED -> COLLECTING -> CLOSE_PENDING -> AUDITING -> terminal`

and `campaign_ownership.transition_state()` already owns compare-and-update and immutable first terminal cause.

The token-state owner already permits:

- `WINDOW_1H_CONTINUING -> WINDOW_1H_CLOSED`;
- terminal transitions such as `FAILED` when an execution failure requires them.

Checkpoint 6 should reuse these owners or narrow them safely rather than creating a parallel state table or direct uncontrolled update path.

## Important non-blockers

- No new memory engine is required.
- No new episode/fingerprint owner is required.
- No new Scheduler job or retry policy is required.
- No schema or migration is required.
- Campaign Scheduler-work terminal synchronization is already present.
- Exact continuation-job -> campaign-window ownership is already durable through the V2 stage-scoped Scheduler-work projection.
- The successful close is the final planned first-hour job, so this checkpoint does not need to create further first-hour work.
- 4h must not be scheduled or activated by this reconciliation.

## Required repair direction

1. after a successful exact `CONTINUATION_CLOSE`, derive the campaign-window terminal classification from authoritative physical-memory/clean-object truth;
2. bind/advance the exact owned campaign `WINDOW_1H` from `CLOSE_PENDING` through `AUDITING` to that terminal state;
3. advance the exact owning token slot once from `WINDOW_1H_CONTINUING` to `WINDOW_1H_CLOSED` on successful first-hour completion regardless of clean/dirty/no-promotion result;
4. on token-local first-hour execution failure, keep the exact window `BLOCKED` and reconcile only that token slot to a truthful terminal failure state;
5. on run-wide cancellation/stop, ensure every affected active first-hour token slot no longer remains `WINDOW_1H_CONTINUING`, without overwriting an earlier terminal cause or touching a completed peer;
6. retain Scheduler terminal synchronization and zero-retry behavior unchanged;
7. prove no pending/running/cooled/locked first-hour Scheduler work remains after terminal reconciliation;
8. prove no 4h Scheduler work is created.

## Money-usefulness contribution

A memory corpus is not operationally trustworthy if the market evidence says the first hour finished while the lifecycle graph says the token is still collecting it. Exact window/token terminal reconciliation makes completed first-hour memories attributable, prevents stale active-state truth from contaminating later rotation or continuation logic, and gives future 4h policy a trustworthy predecessor boundary.

This improves reliability and future money-usefulness but does not prove profitability or authorize any financial action.

## What this checkpoint improves after repair

- exact agreement between physical first-hour memory and campaign-window state;
- exact agreement between first-hour completion/failure and token-slot state;
- token-local failure isolation;
- run-wide cancellation truth;
- trustworthy predecessor state for any later 1h->4h policy review;
- terminal reports that no longer coexist with stale `WINDOW_1H_CONTINUING` state.

## What remains locked

No live first-hour run, fresh authorization/wrapper, 4h activation, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, live wallet/private keys/real funds/execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof required

Focused RED/GREEN proof must establish at minimum:

- successful clean first-hour close currently leaves window/token lifecycle state stale before repair;
- successful clean promotion ends with exact campaign window `CLEAN_PROMOTED` and exact token slot `WINDOW_1H_CLOSED`;
- successful dirty first-hour close ends with exact window `DIRTY` and token slot `WINDOW_1H_CLOSED`;
- successful non-promoted clean-data first-hour close ends with exact window `NO_PROMOTION` and token slot `WINDOW_1H_CLOSED`;
- token-local first-hour failure blocks only that exact window and terminalizes only that token's active first-hour slot;
- run-wide cancellation removes stale first-hour-active state without altering already terminal/completed peers;
- first terminal cause and exact identity are immutable/idempotent;
- Scheduler job and campaign Scheduler-work terminal parity remains intact;
- no active first-hour work remains after reconciliation;
- no `WINDOW_4H` work/window is created;
- Checkpoints 1-5 and directly affected campaign/Scheduler regressions remain green.

## Functionality Risks / Setbacks / Efficiency Blockers

- Terminal state must come from authoritative memory/episode quality, not a convenient pipeline label.
- Success and execution failure are different: a valid close with no clean promotion is `NO_PROMOTION`; an execution/continuity/source failure is `BLOCKED` or cancellation, never silently converted to a normal no-promotion result.
- Token-slot closure must not accidentally become 4h authorization.
- A peer token must never be terminalized because another token failed.
- Run-wide cancellation must preserve any window/token already terminal and must not replace its first terminal cause.
- Existing `bind_1h_memory_window()` can walk earlier window states; the operational success path already proves `CLOSE_PENDING`, so implementation should preserve that stronger boundary instead of weakening it.

## Next permitted action

Design the bounded Checkpoint-6 window/token terminal-reconciliation repair, then implement with focused TDD proof. Do not begin a 4h policy change or operational authorization until Checkpoint 6 closes PASS.

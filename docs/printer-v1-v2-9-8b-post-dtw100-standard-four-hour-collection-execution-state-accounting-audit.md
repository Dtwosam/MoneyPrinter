# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Collection Execution / State / Accounting Audit

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_COLLECTION_EXECUTION_STATE_ACCOUNTING_AUDIT_BLOCKED_REPAIR_DESIGN_REQUIRED`

The existing factory already contains reusable, previously proven 4h snapshot/close execution primitives, Source Governor-backed collection, phase/cumulative budget checks, Central Scheduler claim/terminal operations, and generic campaign Scheduler-work synchronization.

The standard two-token campaign path is **not yet composition-complete for collection execution**. Four specific campaign/state/accounting gaps require a narrow design before production repair:

1. campaign `WINDOW_4H` active-state transitions are not wired to long-window Scheduler claims;
2. lifecycle reservation accounting does not include `LONG_CONTINUATION_*` work;
3. token-local and run-wide campaign-window terminal cleanup remains `WINDOW_1H`-only;
4. the adopted categorical two-token fairness round is not represented by the current pending-step selector.

This audit authorizes no code, source call, runtime, proof, real 4h collection, or activation.

## Baseline

Audit baseline:

`7c73aad865d0ba832e6be3514add27fe33b770f5`

This baseline includes:

- Slice B1 campaign handoff PASS;
- Slice B2 planning + exact stage-scoped Scheduler ownership PASS;
- B2 closeout documentation.

No production file, test, DB, runtime artifact, Scheduler row, source row, memory row, or authorization was changed by this audit.

## Current-owner map

### Reusable / already present

The canonical one-command factory already:

- selects pending run steps and claims the exact Central Scheduler job before work;
- synchronizes an existing V2 stage-scoped campaign Scheduler-work projection from canonical Scheduler truth;
- dispatches `LONG_CONTINUATION_SNAPSHOT` and `LONG_CONTINUATION_CLOSE` through `_execute_long_4h_step`;
- reuses `_execute_snapshot` and governed preclose context collection rather than creating a second 4h collector;
- enforces 4h phase and cumulative lifecycle request ceilings before a long step;
- calculates long-step projected request demand;
- records source request/response/failure provenance through the shared governed snapshot/context paths;
- completes/fails/cancels canonical Scheduler jobs and synchronizes campaign Scheduler-work terminal state;
- isolates ordinary token-local run-step failures by cancelling only that token's remaining pending run steps;
- performs run-wide pending-job cancellation on shared stop;
- contains the existing physical 4h close, context, E2Q, Lane Q and E2Z quality path.

These owners should be reused. No second collector, Scheduler, Source Governor path, or 4h close engine is justified.

## Finding 1 — campaign WINDOW_4H active-state truth is not wired

The factory invokes:

- `_mark_owned_continuation_window_collecting(...)` after Scheduler claim;
- `_mark_owned_continuation_window_close_pending(...)` after Scheduler claim.

Those helpers are explicitly first-hour-only:

- `_owned_continuation_window_for_job` requires `stage_id='WINDOW_1H'` and `window_kind='WINDOW_1H'`;
- collecting transition runs only for `CONTINUATION_SNAPSHOT`;
- close-pending transition runs only for `CONTINUATION_CLOSE`.

Therefore a B2-created campaign `WINDOW_4H` can remain `PLANNED` while its long-window Scheduler jobs are actually RUNNING/SUCCEEDED, and a claimed long close cannot move it to `CLOSE_PENDING`.

This is a truthful-state blocker, not a collector blocker.

## Finding 2 — long-window lifecycle reservation accounting is missing

`_projected_requests_for_step` already models long-window request demand:

- ordinary long snapshot: bounded request projection;
- opening long snapshot: expanded opening-context projection;
- long close: expanded close/context projection.

`_enforce_budgets_before_step` also applies 4h phase and cumulative lifecycle ceilings.

But `_lifecycle_reservation_records_for_step` returns reservation records only for:

- `SNAPSHOT`;
- `WINDOW_CLOSE`;
- `CONTINUATION_SNAPSHOT`;
- `CONTINUATION_CLOSE`.

It excludes:

- `LONG_CONTINUATION_SNAPSHOT`;
- `LONG_CONTINUATION_CLOSE`.

So long-window work currently has budget projection but no matching lifecycle-reservation evidence in the verification/accounting stream. This would make two-token 4h accounting incomplete even if collection itself succeeded.

The existing measured-transport mapping is intentionally 15m-specific and must not be silently repurposed as a 4h contract. The repair design must derive long reservation identities from the existing long-step request projection/context ownership without inventing a second transport counter.

## Finding 3 — token-local and shared campaign cleanup are WINDOW_1H-only

### Token-local failure

On a failed long step, the factory already:

- marks the run step FAILED;
- fails the Scheduler job with zero retry;
- synchronizes campaign Scheduler-work state;
- cancels only that token's remaining pending run steps and Scheduler jobs.

However campaign-window terminalization is invoked only when the failed step kind is:

- `CONTINUATION_SNAPSHOT`; or
- `CONTINUATION_CLOSE`.

The terminal resolver itself is `WINDOW_1H`-specific.

Therefore a failed token's campaign `WINDOW_4H` may remain active after all its long Scheduler work has terminalized.

### Shared safe stop

Run-wide cleanup calls `_cancel_owned_continuation_windows_for_run`, but that function filters:

- `stage_id='WINDOW_1H'`;
- `window_kind='WINDOW_1H'`.

It cannot cancel/reconcile nonterminal campaign `WINDOW_4H` rows after a shared budget/integrity/operator stop.

The generic Scheduler-work synchronization itself is reusable; the missing part is campaign-window/token-slot lifecycle reconciliation for the 4h stage.

## Finding 4 — adopted two-token fairness round is not implemented/proven

The factory's current work selector reads one pending run step with:

`ORDER BY scheduled_for, id LIMIT 1`

and then claims that exact Scheduler job.

The generic Scheduler selector separately orders due jobs by categorical/effective job priority, scheduled time, creation time, and id. Neither path maintains the adopted campaign fairness-round fact: when both tokens are eligible for ordinary service in a fairness round, both must be offered service before either receives a second ordinary non-close unit.

Static inspection does **not** prove real starvation. Fixed cadence timestamps can naturally interleave many current cases. But the adopted contract is not represented explicitly and there is no two-token 4h fairness proof.

This is therefore `NOT_IMPLEMENTED_OR_PROVEN`, not a claim that an observed run starved a token.

The repair must remain categorical. No score, rank, confidence, weighted priority total, or hidden numeric preference may be introduced.

## What is not a blocker in this checkpoint

The following already exist and should not be rebuilt:

- 4h cadence policy;
- B2 exact two-token long-window planning;
- B2 `WINDOW_4H` stage-scoped Scheduler ownership;
- canonical Scheduler enqueue/claim/complete/fail/cancel primitives;
- generic campaign Scheduler-work state synchronization;
- shared governed snapshot collector;
- governed opening/closing context collection;
- 4h phase/cumulative budget enforcement;
- physical `WINDOW_4H` close primitive;
- forced closing-snapshot rule;
- E2Q/Lane Q/E2Z 4h quality primitives.

The unrelated historical one-token E2Z replay assertion documented in the B2 closeout remains outside this checkpoint unless a later close-boundary audit proves it affects the required campaign path.

## Money-usefulness contribution

This audit prevents a misleading implementation where both tokens appear to have 4h jobs but campaign state, source reservations, fairness, and terminal cleanup are not trustworthy.

Repairing these gaps will make four-hour observations more useful for money learning because Printer can distinguish a genuinely completed two-token path from partial, unfair, unaccounted, or orphaned long-window work.

The audit itself creates no new market evidence and proves no profitability.

## What this checkpoint improves

- identifies the exact reuse boundary instead of proposing a second collector;
- separates Scheduler-work truth from campaign-window lifecycle truth;
- identifies missing long-window reservation accounting despite existing request budgets;
- identifies the exact 1h-only cleanup assumptions that would orphan 4h campaign state;
- distinguishes unproven fairness from alleged observed starvation.

## What remains locked

Still locked:

- implementation of these repairs;
- source fetching;
- Scheduler/runtime execution;
- real `WINDOW_4H` collection;
- operational authorization;
- `WINDOW_12H` / `WINDOW_24H`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallet, signing, live execution, real funds.

## Proof/test required after approved implementation

Minimum sufficient offline/TDD proof must establish:

- first long snapshot claim moves only its exact campaign `WINDOW_4H` `PLANNED -> COLLECTING`;
- long close claim moves only its exact campaign `WINDOW_4H` `COLLECTING -> CLOSE_PENDING`;
- every long governed operation has exact lifecycle reservation identity/count with no duplicate or missing reservation;
- successful/failed/cancelled Scheduler work stays synchronized to its exact campaign work row;
- one token's long-step failure cancels/blocks only that token's 4h lifecycle while its peer remains serviceable;
- shared stop cancels/reconciles both nonterminal 4h campaign windows and leaves zero active owned long Scheduler work;
- two-token fairness obeys the adopted categorical service-round rule and close priority;
- directly affected Checkpoint-3 first-hour ownership/accounting/failure tests remain healthy;
- real 4h collection remains disabled throughout offline proof.

No broad suite is required until the later major implementation/proof closeout unless the repair becomes more cross-cutting than this audit allows.

## Functionality Risks / Setbacks / Efficiency Blockers

- Generalizing first-hour helpers carelessly could regress the already-proven 1h path.
- Recording 4h reservation counts independently from actual long-step request ownership could create accounting drift.
- Fairness logic implemented as numeric priority would violate the no-scoring/no-weighted-policy lock.
- Token-local cleanup that touches the peer would convert an isolated evidence failure into a needless campaign stop.
- Run-wide cleanup that terminalizes Scheduler work without campaign-window parity would preserve orphaned lifecycle truth.
- A repair that creates a second 4h collector or private loop would violate Source Governor/Central Scheduler ownership and increase maintenance cost.

## Next permitted task

A separate **standard four-hour collection execution/state/accounting repair design** may begin.

The design must be narrow and reuse current owners. It must not enable real collection, run sources, mutate the DB operationally, or enter the 4h close/memory/terminal-reconciliation checkpoint early.

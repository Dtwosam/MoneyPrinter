# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Collection Execution / State / Accounting Repair Design

## Design verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_COLLECTION_EXECUTION_STATE_ACCOUNTING_REPAIR_DESIGN_PASS`

Implement one narrow offline repair around the existing long-window collector. The canonical data/source/Scheduler path remains unchanged. The repair adds the missing 4h campaign-window state hooks, lifecycle-reservation observations, token-local/shared 4h lifecycle cleanup, and categorical two-token service fairness.

This design does not authorize source fetching, runtime execution, real `WINDOW_4H` collection, 4h close/memory terminal composition, 12h/24h work, retrieval, decisions, positions, or financial capability.

## Baseline

Design baseline:

`fe3533500a8e38491e4e6b0edfefa6c8fd5d1a6d`

Controlling audit:

`docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-collection-execution-state-accounting-audit.md`

Audit verdict:

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_COLLECTION_EXECUTION_STATE_ACCOUNTING_AUDIT_BLOCKED_REPAIR_DESIGN_REQUIRED`

## Canonical owners to preserve

### `src/printer_v1/operator_cli/one_command_15m_factory.py`

Remains the collection orchestration owner for this repair. It already owns:

- pending run-step service;
- Central Scheduler claim/complete/fail/cancel calls;
- canonical snapshot/context execution;
- Source Governor-backed lifecycle source work;
- phase/cumulative budget enforcement;
- campaign Scheduler-work synchronization;
- token-local and run-wide cleanup hooks.

The repair should stay here unless an existing helper must be imported. Do not create a second 4h runner or collector.

### `src/printer_v1/operator_cli/campaign_ownership.py`

Remains the authority for generic campaign state transitions and V2 stage-scoped Scheduler-work projection. No new ownership table, state vocabulary, or schema is required.

### `src/printer_v1/operator_cli/one_token_4h_runtime.py`

Retains B2 planning plus existing 4h close/quality primitives. This checkpoint must not redesign its cadence, physical close, E2Q, Lane Q, or E2Z behavior.

### `src/printer_v1/scheduler/scheduler.py`

Retains canonical Scheduler job truth and claim/terminal operations. The fairness repair must not replace Scheduler ownership or create a private execution loop.

## Repair 1 — stage-exact lifecycle window resolution

Introduce one private stage-exact resolver in the canonical factory, conceptually:

`_owned_lifecycle_window_for_job(... expected_stage, expected_window_kind ...)`

It must require exactly one V2 stage-scoped campaign Scheduler-work owner with:

- `work_scope='WINDOW_LIFECYCLE'`;
- exact `stage_id`;
- `target_category='CAMPAIGN_WINDOW'`;
- non-null exact token slot/window/factory-run identities;
- `target_identity == window_id`;
- exact campaign/run/cycle/token-slot campaign window;
- exact expected `window_kind`.

Ambiguous, missing, cross-stage, cross-slot, cross-window, or mismatched ownership fails closed.

Preserve the existing first-hour helper as a compatibility wrapper around the generic resolver. Add a separate 4h wrapper for `stage_id='WINDOW_4H'` / `window_kind='WINDOW_4H'`.

This avoids duplicating ownership SQL while keeping first-hour behavior explicit.

## Repair 2 — truthful WINDOW_4H active-state transitions

Reuse the existing campaign `window` state machine.

### Long snapshot claim

When the exact claimed step is `LONG_CONTINUATION_SNAPSHOT` and has an exact 4h campaign owner:

- `PLANNED -> COLLECTING` on first real long collection claim;
- exact replay while already `COLLECTING` is idempotent;
- any other state conflicts fail closed.

Do not transition on planning/enqueue alone.

### Long close claim

When the exact claimed step is `LONG_CONTINUATION_CLOSE`:

- require exact owned `WINDOW_4H`;
- `COLLECTING -> CLOSE_PENDING`;
- exact replay while already `CLOSE_PENDING` is idempotent;
- `PLANNED`, terminal, wrong-window, or wrong-stage close claims fail closed.

This checkpoint stops at `CLOSE_PENDING`. It does **not** bind the physical 4h memory row or classify clean/dirty/no-promotion success; that belongs to the later close/memory/terminal-reconciliation checkpoint.

Existing 1h claim transitions remain unchanged.

## Repair 3 — long-window lifecycle-reservation accounting

Do not modify the 15m-specific `LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND` mapping into a hidden cross-window policy.

Extend the canonical factory reservation-record builder to recognize long work using the already-approved `_projected_requests_for_step` count.

Required long families:

- ordinary `LONG_CONTINUATION_SNAPSHOT` -> `LONG_CONTINUATION_SNAPSHOT_OBSERVATION`;
- opening `LONG_CONTINUATION_SNAPSHOT` (`*_snapshot_000`) -> `LONG_CONTINUATION_OPENING_OBSERVATION`;
- `LONG_CONTINUATION_CLOSE` -> `LONG_CONTINUATION_CLOSE_OBSERVATION`.

The number of reservation records must equal the exact already-derived projected request count for that step. Under the current policy this preserves the existing bounded shapes (ordinary/opening/close) without inventing a new source budget.

Each record keeps the existing identity shape:

- run id;
- Scheduler job id;
- step key/kind;
- exact token/pair;
- reservation ordinal;
- categorical operation family.

These remain verification/accounting observations. They do not execute, reserve, retry, or expand Source Governor calls.

## Repair 4 — exact 4h token-local failure/cancel reconciliation

Add a 4h collection failure/cancel reconciler limited to active campaign `WINDOW_4H` lifecycles.

Supported collection-terminal states in this checkpoint:

- `BLOCKED` -> token slot `FAILED`;
- `CANCELLED` -> token slot `MANUAL_REVIEW`.

Required preconditions:

- exact campaign/run/cycle/slot/token/pair ownership;
- `window_kind='WINDOW_4H'`;
- token slot currently `WINDOW_4H_CONTINUING` unless replaying the exact terminal state/cause;
- window currently one of `PLANNED`, `COLLECTING`, `CLOSE_PENDING`, `AUDITING` unless replaying exact terminal truth;
- no conflicting first terminal cause.

The exact window and token slot terminalize atomically with one immutable first cause.

Do not support successful 4h terminal states here. Successful clean/dirty/no-promotion reconciliation requires the later physical-close/memory checkpoint.

### Token-local failure path

When a `LONG_CONTINUATION_SNAPSHOT` or `LONG_CONTINUATION_CLOSE` fails:

- preserve the current run-step failure;
- fail its Scheduler job with zero retry;
- synchronize campaign Scheduler-work truth;
- cancel/synchronize only that token's remaining pending run/Scheduler work;
- reconcile only that token's exact 4h campaign window to `BLOCKED` and slot to `FAILED`;
- leave the peer window/slot/work serviceable unless a shared integrity/budget stop independently applies.

## Repair 5 — shared 4h safe-stop reconciliation

Generalize run-wide owned-window cleanup so it can reconcile both exact lifecycle stages without changing first-hour behavior.

For this checkpoint, shared cleanup must include nonterminal V2 stage-scoped:

- `WINDOW_1H` using the already-proven first-hour owner;
- `WINDOW_4H` using the new 4h failure/cancel owner.

After a run-wide non-normal stop:

- pending Scheduler jobs are cancelled through the canonical Scheduler owner;
- campaign Scheduler-work rows synchronize from canonical Scheduler truth;
- every nonterminal owned `WINDOW_4H` becomes `CANCELLED`;
- its token slot becomes `MANUAL_REVIEW`;
- already terminal exact state/cause replays idempotently;
- conflicting terminal truth fails closed.

No automatic successor or restart is created.

## Repair 6 — categorical two-token WINDOW_4H fairness selection

The adopted fairness contract must become explicit without becoming a score/rank system.

Implement one private pending-step selector used by the canonical factory. It must preserve current behavior outside exact campaign-owned `WINDOW_4H` work.

### Activation boundary

The special selector applies only to pending run steps whose Scheduler jobs have exact V2 stage-scoped ownership for the current campaign/run/cycle and:

- `work_scope='WINDOW_LIFECYCLE'`;
- `stage_id='WINDOW_4H'`;
- exact token slot/window/factory run.

Unowned/historical/non-4h work keeps the existing selection behavior.

### Eligibility

A 4h step is service-eligible only when its canonical Scheduler `scheduled_for` is due at the selection time.

If no 4h step is due, preserve the existing earliest-scheduled behavior so the factory can sleep until the next boundary.

### Categorical order among due 4h work

1. due `LONG_CONTINUATION_CLOSE` before ordinary long snapshots; among due closes, earliest deadline first;
2. for ordinary due long snapshots, token slot that has received less actual service in the current 4h window first;
3. older canonical Scheduler job identity;
4. stable token-slot ordinal only as the final tie-breaker.

`service received` is derived from canonical Scheduler evidence for the exact 4h window: long snapshot jobs with a non-null `started_at` count as service attempts. Cancelled-but-never-started jobs do not.

Numeric counts are used only to establish the categorical relation `LESS_SERVICE / SAME_SERVICE / MORE_SERVICE`; they are not a score, rank, confidence, weight, or performance signal.

### Narrowness rule

Do not reorder an unrelated non-4h path merely because 4h work exists. If a due step belongs outside the exact standard 4h campaign scope, preserve existing owner behavior unless a later explicit scheduler-design lane changes it.

## No change to source execution

`_execute_long_4h_step` continues to use:

- the existing governed snapshot adapter path;
- the existing opening context collection;
- the existing closing context collection;
- exact token/pair run-step identity;
- existing 4h close/quality code.

No source adapter, endpoint, retry policy, transport ceiling, or provider contract changes in this repair.

## No change to budgets

Keep:

- B2 policy-derived two-token ceilings;
- existing long-step `_projected_requests_for_step` semantics;
- 4h phase budget checks;
- cumulative lifecycle budget checks;
- zero Scheduler/source retries where currently required.

Reservation observations must match those budgets; they must not redefine them.

## TDD / minimum proof

Create focused RED tests before production edits. A valid RED must compile and fail for missing 4h composition behavior, not broken fixtures or runner infrastructure.

Minimum GREEN proof:

1. exact long snapshot claim transitions only its owned `WINDOW_4H` `PLANNED -> COLLECTING` and Scheduler-work `PENDING -> RUNNING`;
2. exact long close claim transitions only its owned `WINDOW_4H` `COLLECTING -> CLOSE_PENDING`;
3. opening, ordinary, and close long steps emit reservation counts equal to their existing projected request counts with the three categorical long operation families;
4. token-A long failure yields A window `BLOCKED` + A slot `FAILED`, cancels/synchronizes A remaining work, and leaves token B active/serviceable;
5. shared stop cancels/reconciles both nonterminal 4h windows, both slots enter `MANUAL_REVIEW`, and zero owned long Scheduler work remains active;
6. same-lane due work alternates service categorically when both tokens are eligible before either receives a second ordinary unit;
7. mixed FAST/NORMAL shared-due boundary serves the less-served eligible token first;
8. a due long close beats ordinary due long snapshot work;
9. no-due 4h case preserves earliest future scheduling behavior;
10. B2 planning/ownership tests remain green;
11. directly affected first-hour Checkpoint-3 collection-state/accounting/failure regressions remain green;
12. canonical Scheduler ownership projection tests remain green;
13. real 4h collection remains disabled and 12h/24h remain locked;
14. `git diff --check` and compile pass.

Do not include the unrelated historical one-token E2Z replay assertion in this focused checkpoint unless the implementation unexpectedly touches its close path.

## Expected production scope

Prefer one production file:

- `src/printer_v1/operator_cli/one_command_15m_factory.py`

Touch another production file only if a focused RED proves an existing canonical owner must change; document why before widening scope.

No schema/migration is expected.

## Money-usefulness contribution

This repair makes two-token 4h evidence operationally attributable: Printer can know which token actually received service, whether source capacity was accounted for, whether campaign state matches execution, and whether a failed token was isolated without corrupting its peer.

That improves the trustworthiness of later four-hour memories used to understand continuation, collapse, revival, distribution and liquidity deterioration. It still proves no profitability and authorizes no action.

## What this design improves

- preserves one collector and one Scheduler owner;
- makes campaign state follow actual 4h service rather than planning alone;
- closes long-window accounting visibility;
- makes 4h failure/cancel cleanup exact and token-local where appropriate;
- converts fairness from a narrative requirement into a categorical executable contract.

## What remains locked after implementation PASS

Even a full focused implementation PASS still does not unlock:

- real 4h collection;
- operational source fetching;
- 4h physical close/memory terminal composition at campaign level;
- implementation/proof lane closeout;
- operational 4h rereadiness;
- activation or one-use authorization;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallets, signing, real funds, live execution.

## Functionality Risks / Setbacks / Efficiency Blockers

- A stage-generic ownership resolver must not weaken exact 1h ownership checks.
- Fairness must remain due-work/category based; applying fairness to future/not-due work would distort cadence.
- Counting scheduled or cancelled work as service would make fairness dishonest; only Scheduler-start evidence qualifies.
- Long reservation records must follow the existing projected request count exactly or accounting will drift from budget enforcement.
- Successful 4h terminal reconciliation is deliberately deferred; implementing it here would skip the required close/memory audit.
- Broad refactoring of the large canonical factory would increase risk and credit use without advancing the checkpoint.

## Next task after design adoption

Focused offline TDD implementation of this design only.

Stop after focused proof/closeout. Do not run real 4h collection or enter the close/memory checkpoint until this repair has its own PASS closeout.

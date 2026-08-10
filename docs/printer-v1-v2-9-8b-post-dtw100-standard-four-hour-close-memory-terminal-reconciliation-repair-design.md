# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Close / Memory / Terminal-Reconciliation Repair Design

## Design verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_CLOSE_MEMORY_TERMINAL_RECONCILIATION_REPAIR_DESIGN_PASS`

Implement a narrow standard-campaign composition around the already-proven physical 4h close and clean-object pipeline.

Do not rebuild the collector, physical close, shared context, E2Q, Lane Q, E2Z, clean-object promotion, B2 planning, Scheduler ownership, or historical one-token proof validator.

This design authorizes offline TDD implementation only. It does not authorize source fetching, real `WINDOW_4H` collection, operational authorization, 12h/24h, retrieval, decisions, positions, or financial capability.

## Baseline

Design baseline:

`c8e38a3e4a0f29db0d63623afeafdcd6bf38a42f`

Controlling audit:

`docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-close-memory-terminal-reconciliation-audit.md`

## Reuse law

Preserve these canonical owners unchanged unless a focused RED proves an exact narrow change is required:

- `close_current_run_4h` — physical 4h memory-window close;
- `_execute_long_4h_step` — governed closing snapshot/context + physical pipeline orchestration;
- `build_window_4h_context_evidence` — shared 4h context truth;
- E2Q genuine `WINDOW_4H` classification;
- Lane Q 4h integrity/cadence gate;
- E2Z + `promote_clean_object` — clean episode/fingerprint ownership;
- B2 exact stage-scoped `WINDOW_4H` Scheduler ownership;
- current 4h claim-state transitions and failure/cancel reconciliation;
- Central Scheduler terminal owners and campaign Scheduler-work synchronization.

No schema/migration is expected.

## Repair 1 — authoritative 4h success classification

Add one private 4h classifier in the canonical factory, conceptually:

`_classify_owned_4h_terminal_state(connection, memory_window_row_id, result)`

It must first validate the physical target:

- row exists;
- `window_kind='WINDOW_4H'`;
- exact token/pair identity will later be cross-checked against the campaign window;
- the physical row is closed.

Then derive the categorical terminal state from authoritative DB truth.

### Clean object authority

A complete clean object exists only when one exact `printer_episodes` row and one exact clean fingerprint are bound to the physical 4h window with:

- `episode_kind='WINDOW_4H_CLEAN_MEMORY'`;
- episode `window_kind='WINDOW_4H'`;
- exact physical `memory_window_id`, token and pair;
- `episode_status='COMPLETE'`;
- clean memory/data labels and `do_not_train=0`;
- exact clean fingerprint whose payload identities match episode/window/token/pair/window kind.

Do not infer clean promotion from `lane_k_status`, a report count, or physical `PARTIAL_MEMORY` alone.

If a complete exact clean object exists:

- `E2Z_MEMORY_CREATED` in this exact close's memory-pipeline result -> `CLEAN_PROMOTED`;
- `E2Z_ALREADY_EXISTS` in this exact close's memory-pipeline result -> `ALREADY_EXISTS_IDEMPOTENT`.

A complete clean object with missing/conflicting E2Z event identity fails closed rather than guessing whether this close created or replayed it.

### Dirty authority

If no complete clean object exists and the physical 4h row is dirty/audit-only/do-not-train or has non-clean data quality, classify `DIRTY`.

### No-promotion authority

If the physical 4h row is a clean-data, do-not-train=0 candidate but no complete clean object exists, classify `NO_PROMOTION`.

This preserves lifecycle completion separately from money-memory acceptance.

## Repair 2 — exact successful 4h campaign reconciliation

Add one stage-specific campaign reconciliation owner, preferably in the existing 4h campaign/runtime module rather than the 1h-named module.

Conceptual contract:

`reconcile_4h_terminal_lifecycle(connection, campaign_window_4h_id, terminal_state, terminal_cause, memory_window_row_id)`

Supported successful terminal states:

- `CLEAN_PROMOTED`;
- `DIRTY`;
- `NO_PROMOTION`;
- `ALREADY_EXISTS_IDEMPOTENT`.

Required exact preconditions:

- campaign window exists and `window_kind='WINDOW_4H'`;
- window and token-slot campaign/run/cycle identities match;
- token/pair identities match;
- physical memory row exists and has exact token/pair/`WINDOW_4H` identity;
- active successful path requires campaign window `CLOSE_PENDING`;
- active successful token slot requires `WINDOW_4H_CONTINUING`;
- no conflicting first terminal cause;
- existing `memory_window_row_id` is null or exactly equal to the supplied physical row.

### Transaction rule

The reconciler must use a SAVEPOINT or caller-owned transaction semantics. It must **not** commit an outer transaction.

On fresh success, in one caller-owned transaction:

1. bind `memory_window_row_id` by compare-and-update;
2. transition exact campaign window `CLOSE_PENDING -> AUDITING`;
3. transition exact campaign window `AUDITING -> <terminal_state>` with immutable terminal cause;
4. transition exact token slot `WINDOW_4H_CONTINUING -> WINDOW_4H_CLOSED`;
5. read back exact state/memory/cause/identity;
6. return without committing the caller's outer transaction.

Successful token slots do not receive a failure first-terminal-cause. The campaign window records the terminal outcome cause.

Exact replay is idempotent only when terminal state, cause, memory identity and slot state all match. Any conflict fails closed.

Do not merge collection-stage `BLOCKED/CANCELLED` logic into this successful reconciler unless a focused test proves a common owner is safer; the prior checkpoint's failure owner is already proven.

## Repair 3 — main factory successful LONG_CONTINUATION_CLOSE binding

Add a helper analogous in purpose to the first-hour close binder, but 4h-specific and stage-correct:

`_bind_owned_long_memory_window_at_close(...)`

Inputs:

- canonical long-close Scheduler job id;
- exact physical `memory_window_row_id`;
- exact close result containing the memory-pipeline E2Z event.

Behavior:

1. resolve exact stage-scoped owned campaign `WINDOW_4H` from the Scheduler job;
2. classify authoritative 4h terminal state under Repair 1;
3. verify physical token/pair identity equals campaign window/slot identity;
4. call the 4h successful reconciler under Repair 2;
5. return the exact binding/terminal result for durable close-step reporting.

In the main successful step path:

- after `_execute_long_4h_step` returns a physical `memory_window_id`, update the close step result;
- before `complete_job`, call the 4h binding helper;
- persist the binding result into close-step `result_json`;
- only then complete the canonical Scheduler job;
- synchronize campaign Scheduler-work truth;
- commit step success + campaign binding + Scheduler terminal state together.

A campaign-binding failure must not complete the Scheduler job as success.

The earlier physical close/E2Q/E2Z commits remain truthful independent durable facts; this repair does not pretend those already-committed operations can be rolled back by the later campaign transaction.

## Repair 4 — standard two-window 4h terminal validator

Add a separate standard-campaign validator rather than rewriting `_four_hour_terminal_validation`.

The new validator is enabled only when exact V2 stage-scoped B2 ownership exists for the current campaign/run/cycle/factory-run `WINDOW_4H` set.

### Activation / fail-closed shape

- zero B2 4h campaign windows -> validator disabled; preserve historical validator behavior;
- exactly two exact B2 4h windows -> standard validator enabled;
- any non-zero partial/foreign/ambiguous standard set -> enabled but incomplete/fail closed.

Required exact set for PASS:

- exactly two campaign `WINDOW_4H` rows;
- exactly two distinct token slots and token/pair identities;
- each window has exact stage-scoped Scheduler ownership for its long steps;
- exactly one `LONG_CONTINUATION_CLOSE` per owned window;
- no foreign/duplicate window or close identity.

### Per-token validation

For each owned 4h window independently:

- derive its own tracking lane from its run steps;
- derive expected snapshot count from that lane's `WINDOW_4H` cadence policy;
- count only that token/pair/window's attached long snapshots;
- require exact expected count;
- require long close step `SUCCEEDED`;
- require canonical close Scheduler job and projected campaign work terminal `SUCCEEDED`;
- require physical `memory_window_row_id` and exact physical `WINDOW_4H` token/pair identity;
- require campaign window in one successful terminal state;
- require token slot `WINDOW_4H_CLOSED`;
- require physical/clean-object truth consistent with the campaign terminal state.

Mixed FAST/NORMAL campaigns are therefore valid and use different per-token expected counts where policy requires it.

### Campaign-set validation

PASS additionally requires:

- both token lifecycles terminal regardless of close arrival order;
- zero active owned 4h Scheduler jobs/work rows;
- zero nonterminal owned campaign `WINDOW_4H` rows;
- no dirty outcome counted as clean memory;
- no duplicate clean episode/fingerprint identity;
- pending/running run-step count consistent with terminal campaign closeout.

Return per-token categorical outcome records as well as aggregate completion. Do not aggregate outcomes into a score.

## Repair 5 — final-report validator routing

At final report construction, detect exact standard B2 4h campaign ownership.

If standard ownership is present:

- use the new standard-campaign terminal validator as the authoritative 4h terminal validation;
- do not let the historical one-token validator's `len(close_steps)==1` assumption set the run status;
- preserve the historical validator only as a disabled/not-applicable diagnostic if useful.

If standard ownership is absent:

- keep current `_four_hour_terminal_validation` behavior unchanged.

The older compressed-two-token proof validator also remains unchanged and must not become authoritative for the new standard campaign. If its historical proof configuration is not active, leave it disabled as today.

## No change to physical memory semantics

Do not change:

- `WINDOW_4H` physical duration/cadence policy;
- opening/closing snapshot identity;
- context requirements;
- E2Q thresholds;
- Lane Q thresholds;
- clean-object outcome requirements;
- clean fingerprint construction;
- source request budgets;
- Source Governor behavior;
- Scheduler fairness implemented by the previous checkpoint.

## TDD / minimum sufficient proof

Create focused RED tests before production edits.

A valid RED must compile and fail only for missing standard 4h successful binding/terminal validation while current physical 4h and first-hour contracts remain healthy.

Minimum GREEN proof:

1. clean physical 4h + exact newly-created clean object -> campaign `CLEAN_PROMOTED`, slot `WINDOW_4H_CLOSED`;
2. exact complete pre-existing clean object + E2Z replay -> `ALREADY_EXISTS_IDEMPOTENT` without duplicate episode/fingerprint;
3. dirty/audit-only physical result -> `DIRTY`, no clean object counted;
4. clean physical candidate without complete clean object -> `NO_PROMOTION`;
5. physical memory token/pair/window-kind mismatch fails before campaign terminalization;
6. fresh success requires `CLOSE_PENDING` + `WINDOW_4H_CONTINUING`;
7. conflicting terminal state/cause/memory replay fails closed;
8. exact terminal replay is idempotent;
9. 4h binding failure prevents Scheduler success terminalization in the composed success path;
10. token A and B close in either order without touching each other's lifecycle;
11. FAST + NORMAL standard set validates each token against its own policy-derived expected snapshot count;
12. exactly two close identities required; missing/duplicate/foreign close fails;
13. standard validator requires zero active owned 4h Scheduler/work rows and zero nonterminal 4h windows;
14. standard validator distinguishes clean, dirty and no-promotion per token without scores;
15. historical one-token 4h terminal validator tests remain green;
16. first-hour close/binding/terminal reconciliation regressions remain green;
17. previous standard 4h planning/state/accounting/fairness tests remain green;
18. real `WINDOW_4H`, `WINDOW_12H` and `WINDOW_24H` collection remain disabled;
19. compile and `git diff --check` pass.

Do not include unrelated historical failures unless a changed owner makes them relevant.

## Expected production scope

Expected narrow scope:

- `src/printer_v1/operator_cli/one_command_15m_factory.py`;
- one existing 4h campaign/runtime owner for successful terminal reconciliation, preferably `src/printer_v1/operator_cli/one_token_4h_runtime.py`.

Tests may add one focused standard 4h close/memory/terminal file and reuse existing fixtures.

No migration/schema/source-contract file is expected.

## Money-usefulness contribution

This repair makes each long-horizon memory outcome attributable all the way from physical evidence to campaign lifecycle truth.

A clean 4h memory can then be counted as clean only when its complete clean object exists; a dirty 4h result remains useful negative evidence without being promoted; a no-promotion result remains honest rather than disappearing; and the campaign can prove both token lifecycles really ended.

That directly improves corpus yield accounting and future historical comparison quality while creating no decision or trading authority.

## What this design improves

- closes the success-path gap left intentionally by the collection-state checkpoint;
- keeps physical close and clean-object owners single and canonical;
- handles mixed-lane two-token standard campaigns correctly;
- preserves historical one-token proof behavior;
- defines truthful transaction boundaries around already-committed physical memory work;
- prevents Scheduler success from outrunning campaign terminal truth.

## What remains locked after implementation PASS

Even after this repair passes offline proof, still locked:

- real 4h collection;
- operational 4h rereadiness/authorization;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, audits, PnL;
- wallets, signing, live execution, real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors.

A later overall standard-4h integration proof/closeout is still required before any operational rereadiness question.

## Functionality Risks / Setbacks / Efficiency Blockers

- A 4h classifier that trusts only nested report JSON can overstate clean memory; DB clean-object identity must be authoritative.
- A reconciler using `with connection:` may commit the caller transaction early; use savepoint/caller-owned transaction semantics.
- Rewriting the historical one-token validator risks regression for no gain; route by exact standard ownership instead.
- A single aggregate cadence expectation breaks mixed FAST/NORMAL campaigns.
- A partial standard B2 ownership set must fail closed, not fall back silently to the historical validator.
- Physical E2Q/E2Z operations are already committed before campaign binding; later campaign failure must report that fact honestly rather than claim rollback.
- `ALREADY_EXISTS_IDEMPOTENT` must require both authoritative existing clean object and exact E2Z replay evidence.

## Next task after design adoption

Focused offline TDD implementation of this design only.

Stop after its bounded proof and closeout. Do not run real 4h collection or begin operational activation.

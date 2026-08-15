# Printer V1 V2-9.8B — Shared-Terminal Pre-Lifecycle Zero-Attempt Repair Closeout

## Verdict

`V2_9_8B_SHARED_TERMINAL_PRE_LIFECYCLE_ZERO_ATTEMPT_REPAIR_CLOSEOUT_PASS_READY_FOR_HISTORICAL_RECONCILIATION_AUDIT_DESIGN`

## Lane identity

- Starting audit commit: `8fbfb088b70d8849d558f1c8b05f3bb6694958de`
- Required parent anchor: `c7279622247a7e18ff2b29c6ebc63597d4774b92`
- Branch: `agent/v2-9-8b-shared-terminal-pre-lifecycle-repair`
- Design commit: `c9f5e1cc1a4026646ca34a4fafd188f93a0cbd60`
- Safety-amended design commit: `41735be6bf7af39111a3650ff918b9f5c4e9c56c`
- Focused RED workflow commit: `ae2a90425165e33ecc164b8b7c764748b096ed70`
- Final focused-test contract commits: `6ad44930c1ef8749450202cac38fe2905607d843`, `dcfcf7ccc37da26efcedb2d46d5ed345326202cf`
- Verified implementation commit: `683f39d4b88951f8cd925e42f7764a1e58d41804`

Historical execution `20260814T172224Z-490856f405bf` was not mutated or rewritten by this lane.

## Defect confirmation

The audit finding was independently confirmed before implementation.

`finalize_four_token_shared_terminal()` previously accepted only:

1. `TWO_CYCLE_COMPLETION`; or
2. `ONE_CYCLE_HONEST_NO_ADMISSION`, which required exactly one terminal proposed-Cycle-2 pre-admission attempt row.

A legitimate Cycle-1 failure before opening planning completes can have one Cycle-1 row and zero Cycle-2 pre-admission attempts. That state was structurally reachable but had no Phase-B classification.

The repair deliberately does **not** accept `one cycle + zero attempts` by itself.

## Implemented contract

### Positive factory witness

The canonical one-command factory now owns one narrow control-flow witness:

- `four_token_cycle_one_opening_completed` starts false;
- it becomes true only after Cycle-1 `_plan_opening_jobs()` returns successfully;
- Phase A receives `terminal_phase='CAMPAIGN_PRE_LIFECYCLE'` only for Cycle 1 when terminalization occurs while that witness remains false.

### Durable provenance

Migration `056_four_token_pre_lifecycle_terminal_provenance.sql` adds immutable table:

`printer_four_token_pre_lifecycle_terminal_provenance`

The marker is accepted only for exact campaign/run/factory/Cycle-1 ownership with:

- Cycle 1 only;
- exactly two Cycle-1 slots;
- zero Cycle-2 attempts;
- zero Cycle-2 cycles;
- zero Cycle-1 campaign lifecycle windows;
- live pre-terminal Cycle 1;
- non-empty terminal cause.

The migration also:

- forbids marker update/delete;
- forbids a later Cycle-2 attempt that contradicts an existing pre-lifecycle marker;
- forbids deletion of pre-admission attempt history.

### Phase A

`reconcile_four_token_cycle_terminal()` now accepts optional `terminal_phase` and records the marker only when the positive factory witness and persisted structural guards agree. No explicit phase means no provenance is created.

### Phase B

`finalize_four_token_shared_terminal()` now preserves both previous accepted shapes and adds:

`ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT`

That shape requires:

- exactly one terminal Cycle 1;
- zero proposed-Cycle-2 attempt rows;
- exactly one matching immutable pre-lifecycle provenance row;
- provenance cause matching Cycle 1's immutable terminal cause;
- zero Cycle-1 campaign windows;
- all existing zero-active-work, zero-running-step and shared-cleanup guards.

Missing, ambiguous or contradictory evidence continues to fail closed.

## RED proof

Workflow run `31853811127`, job `94934627770`, on the unimplemented contract proved the intended missing behavior:

- the exact zero-attempt shape failed at the old one-cycle Phase-B guard; and
- migration 056 did not exist.

The RED failed for the intended defect only; no unrelated import/setup failure was used as evidence.

## Focused GREEN / bounded disposable proof

Workflow run `31854236035`, job `94935837025`, executed the implementation and the minimum risk-based verification set:

- `tests/test_v2_9_8b_shared_terminal_pre_lifecycle_zero_attempt.py`
- `tests/test_v2_9_8b_shared_terminal_pre_lifecycle_factory_integration.py`
- `tests/test_v2_9_8b_four_token_factory_terminal_integration.py`
- `tests/test_v2_9_8b_four_token_gate_g_two_phase_terminal.py`
- `tests/test_v2_9_8b_pre_admission_later_cycle_callback.py`

Result:

`13 passed in 12.48s`

Also passed:

- `py_compile` for the two modified production Python owners;
- `git diff --check`.

The factory integration proof injects an opening-planning failure on disposable SQLite and proves the real canonical path creates the marker, terminalizes Cycle 1, invokes shared cleanup once and reports `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT`.

No live source fetch, discovery run, memory generation, authoritative operational Scheduler execution, or authoritative DB mutation occurred.

## Independent post-implementation inspection

Compared `8fbfb088...` through `683f39d...`.

Final net changes are limited to six intended files:

1. this lane's design document;
2. migration 056;
3. `four_token_factory_adapter.py`;
4. `one_command_15m_factory.py`;
5. focused adapter/migration tests;
6. focused real-factory integration test.

The temporary GitHub Actions verifier is absent from the final implementation tree.

The prior slot-order/rollback repair was not modified.

The outer shared terminal owner still supplies `lifecycle_started=True` to `reconcile_campaign_terminal()`. Inspection confirmed that field is report metadata in the unified terminal owner and does not branch or weaken terminal reconciliation. This lane therefore leaves that existing outer-owner semantic unchanged; the new immutable provenance row is the authoritative discriminator for `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT`.

## Authoritative DB / historical evidence

This lane did not touch the authoritative database.

The completed audit identity before this repair remains historical evidence:

`sha256 5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`

The consumed execution `20260814T172224Z-490856f405bf` predates migration 056. The repair must not manufacture or silently backfill provenance into that execution.

## Money-usefulness contribution

This repair prevents a legitimate early four-token failure from consuming bounded operational authority while leaving durable campaign ownership stranded. Cleaner terminal behavior reduces recovery friction and makes later memory-growth evidence more trustworthy. It does not itself create trading or financial capability.

## What improved

- exact classification of legitimate Cycle-1 pre-lifecycle zero-attempt terminals;
- positive runtime provenance instead of inference from empty tables;
- durable immutable evidence for the new shape;
- fail-closed contradiction protection between provenance and Cycle-2 attempt history;
- recurrence protection for future early Cycle-1 failures;
- preservation of the existing two-cycle and honest-no-admission terminal paths.

## What remains locked

This closeout does not authorize:

- authoritative historical cleanup/reconciliation;
- a fresh operational proof;
- new four-token authorization;
- six-token widening;
- 12h/24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events/audits;
- PnL.

All V1 Source Governor, Central Scheduler, clean-memory and paper-only restrictions remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The historical stranded execution has no migration-056 marker because it predates the repair. It requires a separate evidence-backed historical reconciliation lane.
2. Migration 056 changes the canonical schema identity when applied to the authoritative database; any authorization bound to the old DB identity becomes stale and must not be reused.
3. The new factory witness intentionally covers failure before Cycle-1 opening planning completes. It must not be broadened into a generic zero-attempt classifier.
4. The outer terminal reconciliation's existing `lifecycle_started` report field remains broader than the new marker's precise `CAMPAIGN_PRE_LIFECYCLE` classification; it is report-only and was not widened in this lane.
5. No broad regression suite was run because the implementation surface was narrow and the focused dependency set passed. A broader suite is reserved for a later major checkpoint/pre-operational authorization gate if required by the active build order.

## Safest next lane

`V2-9.8B — Historical Execution 20260814T172224Z-490856f405bf Reconciliation Audit & Design`

That lane must be audit/design first. It should:

1. revalidate no live owner/lease/process exists;
2. bind the preserved audit and immutable operator artifacts to the exact historical execution;
3. determine whether the historical evidence is sufficient to justify an execution-scoped provenance/backfill/reconciliation procedure without weakening the new production classifier;
4. enumerate the minimum authoritative mutations and post-mutation zero-state requirements;
5. design a disposable-copy proof before any authoritative mutation.

Stop before authoritative cleanup or fresh operational authorization until that audit/design passes.

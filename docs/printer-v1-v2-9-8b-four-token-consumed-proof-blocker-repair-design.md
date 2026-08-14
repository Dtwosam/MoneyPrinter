# Printer V1 V2-9.8B Four-Token Consumed-Proof Blocker Repair Design

Date: 2026-08-14

Baseline audit commit: `37107df32100a6639734220ef5fd211b4e8e2220`

Historical consumed launch HEAD: `d66dc3d9aacf79c4daa09b01dc9a7cf8cdaee91d`

Verdict:

`V2_9_8B_FOUR_TOKEN_CONSUMED_PROOF_BLOCKER_REPAIR_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`

## Boundary

Design/specification only. This document does not authorize implementation, create or review a fresh proof authorization, run Printer, perform discovery/source fetching, mutate the authoritative DB, generate memory, rerun the consumed proof, or unlock any later retrieval/trading capability.

The consumed authorization remains permanently consumed.

## Sources used

Use this design inside the active Printer V1 source stack, including:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-python-builder-guide.md`
- `docs/printer-v1-v2-9-8b-four-token-bounded-capacity-proof-integration-design.md`
- `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-design-amendment.md`
- `docs/printer-v1-v2-9-8b-four-token-consumed-proof-blocker-audit.md`

## Design decision

Adopt one narrow three-part repair inside the existing owners:

1. make cycle terminal reconciliation stage-scope aware without weakening Scheduler ownership checks;
2. release the pre-admission SQLite write transaction before later-cycle candidate supply begins;
3. preserve a bounded stable underlying cause when later-cycle supply throws an exception.

No new coordinator, new Scheduler path, new source path, new retry behavior, new database migration, or public capacity change is justified.

## Options considered

### Option A — narrow three-part repair in existing owners — ACCEPTED

Repair the two proven implementation defects and one proven diagnostic defect where they already live.

Advantages:

- smallest production diff;
- preserves Central Scheduler and Source Governor ownership;
- preserves the exact-two admission contract;
- preserves the existing pre-admission schema;
- gives focused TDD seams;
- avoids reopening the four-token architecture.

### Option B — reconcile only `WINDOW_LIFECYCLE` rows — REJECTED

Filtering terminal reconciliation down to lifecycle rows would avoid the current false positive, but it would make terminal closeout blind to valid campaign-owned discovery, handoff, and cleanup Scheduler work. That weakens the fail-closed ownership model instead of repairing it.

### Option C — add a new coordinator/diagnostic subsystem or migration — REJECTED

The existing owners and TEXT terminal fields can represent the required behavior. A new coordinator, schema, or diagnostic subsystem would expand the lane without evidence that it is necessary.

## Repair 1 — stage-scope-aware terminal reconciliation

Owner:

`src/printer_v1/operator_cli/four_token_factory_adapter.py`

### Required contract

For every campaign Scheduler ownership row associated with the reconciled cycle:

- `ownership_contract_version` must equal `V2_STAGE_SCOPED`;
- `work_scope` must be one of the exact canonical campaign scopes:
  - `DISCOVERY_SELECTION`
  - `FIRST_15M_HANDOFF`
  - `WINDOW_LIFECYCLE`
  - `TERMINAL_CLEANUP`
- `scheduler_job_id` must be non-null and continue to resolve through the existing fail-closed Scheduler reconciliation rules.

The implementation should reuse an existing canonical scope constant/helper if one already exists at the implementation baseline. If no reusable source exists, define one narrow immutable allowlist in the owning module rather than adding a parallel abstraction.

### Must not change

- Do not ignore non-window rows.
- Do not accept arbitrary/unknown work scopes.
- Do not weaken ownership-version checks.
- Do not tolerate missing Scheduler job identity.
- Do not change cancellation/terminal handling for genuinely active or orphaned work.

## Repair 2 — release pre-admission write ownership before supply I/O

Owner:

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

Relevant callback:

`_build_later_cycle_discovery_callback()`

### Required phase boundary

#### Phase A — establish durable pre-admission authority

Using the operational connection:

1. create/resolve the scheduled pre-admission attempt;
2. claim the Central Scheduler job;
3. mark the pre-admission attempt `RUNNING`;
4. commit those writes;
5. release the transaction before candidate supply starts.

Preferred implementation: close the outer operational connection after the commit and reopen a fresh connection for the persistence phase. This provides the clearest proof that no outer connection or write transaction is held across later-cycle supply. Retaining an idle connection is acceptable only if focused tests prove it is not in a transaction and cannot retain a write lock; close/reopen is therefore preferred.

The durable `RUNNING` attempt plus claimed Scheduler job remain the authority while supply work executes.

#### Phase B — execute later-cycle supply outside outer DB write ownership

Invoke the existing `supply_owner(...)` only after Phase A is durably committed/released.

Do not change:

- canonical permanent graduated-supply composition;
- source eligibility;
- exact-two policy;
- Source Governor budgets/ownership;
- Central Scheduler ownership;
- retry count/maximum retry policy;
- cycle spacing or four-token capacity contract.

#### Phase C — persist result in a fresh short write boundary

After supply returns, open a fresh operational connection and persist only the required terminal/result state:

- re-read the durable attempt/job authority as needed and fail closed on unexpected state drift;
- insert bounded supply evidence;
- persist the exact pair when exactly two valid candidates are returned, or the existing honest `NO_PAIR` terminal otherwise;
- complete/fail the Scheduler job through the existing owner;
- commit and release promptly.

If supply raises, exception classification happens outside an open DB write transaction; then a fresh operational connection is opened solely to persist the bounded failure terminal and fail the Scheduler job.

### Authority drift rule

If the attempt or Scheduler job is no longer in the expected durable in-progress state when Phase C reopens, do not overwrite the newer durable state and do not admit a pair. Fail closed through the existing ownership/error model.

## Repair 3 — bounded typed later-cycle exception provenance

Owners:

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- reuse existing safe domain error codes/helpers where available.

No migration is required: the current terminal-cause/error TEXT fields are sufficient.

### Required helper behavior

Introduce one small deterministic classifier for exceptions thrown by `supply_owner(...)`.

The persisted cause must:

- be stable and machine-readable;
- use only a bounded safe uppercase identifier alphabet such as `[A-Z0-9_]+`;
- remain short (maximum 128 characters is sufficient);
- preserve an existing stable Printer/domain error code when the exception exposes one through an already-approved safe interface;
- otherwise fall back to a class/category-based identifier, for example `LATER_CYCLE_SUPPLY_EXCEPTION_<SAFE_CLASS_NAME>`;
- be written consistently to the pre-admission attempt terminal cause and Scheduler `last_error`.

The persisted cause must not include:

- raw `str(exc)` for unknown exceptions;
- stack traces;
- source/provider response bodies;
- URLs with query secrets;
- API keys/tokens;
- arbitrary unbounded payload text.

The pre-admission state remains `FAILED`. This provenance improvement does not convert failures into success and does not introduce retries.

### Honest no-pair contract remains unchanged

When supply returns normally but not with exactly two candidates:

- terminal state remains `NO_PAIR`;
- preserve `supply.terminal_cause`, falling back to the existing `NO_EXACT_PAIR` behavior;
- do not route normal scarcity through the exception classifier.

## TDD implementation order

Implementation is authorized only after design approval.

### Slice 1 — reconciliation

RED:

- a cycle with valid mixed `DISCOVERY_SELECTION`, `FIRST_15M_HANDOFF`, and `WINDOW_LIFECYCLE` ownership reproduces the current false-positive rejection.

GREEN:

- valid mixed canonical V2 scopes pass;
- `TERMINAL_CLEANUP` is accepted as canonical;
- unknown scope fails closed;
- wrong ownership version fails closed;
- missing Scheduler job ID fails closed;
- genuinely active/orphaned Scheduler work retains existing fail-closed behavior.

### Slice 2 — transaction boundary

RED:

- demonstrate that the current callback can invoke supply while the outer operational connection remains in a write transaction.

GREEN:

- Scheduler claim and attempt `RUNNING` state are durably visible before supply starts;
- supply is invoked with no outer write transaction held, preferably after the outer connection is closed;
- returned supply is persisted through a fresh short connection;
- exception terminalization also uses a fresh short connection;
- no source/supply call occurs if authority establishment fails.

### Slice 3 — terminal provenance

RED/GREEN:

- normal no-pair remains `NO_PAIR` with the canonical supply terminal cause;
- a known safe domain exception persists its stable bounded code;
- an unknown exception persists only a bounded class/category identifier, not its message/payload;
- attempt terminal cause and Scheduler `last_error` match;
- `max_retries=0` still yields immediate `FAILED` and no cooldown/requeue.

## Minimum verification before implementation closeout

Use risk-based verification only:

- the focused RED/GREEN tests above;
- directly affected four-token/pre-admission/Scheduler ownership tests;
- Python compile checks for changed modules;
- `git diff --check`.

Do not request a broad regression suite during each implementation slice. Broad/full checks belong at repair closeout/pre-proof rereadiness because this repair touches shared operational campaign code.

No live source run, proof, memory generation, fresh authorization, or authoritative DB mutation is part of implementation verification.

## Money-usefulness contribution

The repair makes the next bounded four-token proof measure actual multi-cycle memory-factory capacity instead of failing on a false ownership validator or an avoidable SQLite lock boundary. Bounded terminal provenance also prevents wasting future one-shot attempts on opaque infrastructure failures.

## What this lane improves

- truthful reconciliation of all canonical stage-scoped Scheduler ownership;
- SQLite-safe cycle-2 pre-admission/supply transaction boundaries;
- durable diagnostic precision for genuine later-cycle supply exceptions.

## What this lane still does not unlock

This design does not prove four-token memory growth and does not authorize another attempt. It does not unlock 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, PnL, live wallets, private keys, real funds, paid APIs, scoring/ranking/confidence, or embeddings/vectors.

A fresh four-token authorization remains forbidden until the approved implementation, bounded verification, repair closeout, and independent rereadiness/rereview pass.

## Functionality Risks / Setbacks / Efficiency Blockers

- The exact exception class thrown in the consumed attempt was not durably preserved; the repair must not retroactively claim one.
- Splitting the DB transaction must preserve durable Scheduler/attempt authority across the supply phase and fail closed on unexpected state drift.
- The terminal classifier must remain deterministic and bounded; using arbitrary exception text would create leakage and nondeterminism.
- Reconciliation must fix the scope false positive without making discovery/handoff/cleanup ownership invisible.
- Shared operational campaign code means broad regression belongs at final closeout, not during every RED/GREEN iteration.

## Completion boundary

Design completion means the exact repair contract is approved. It does not authorize a fresh four-token proof.

After approval, the next permitted lane is:

`V2-9.8B FOUR-TOKEN CONSUMED-PROOF BLOCKER TDD IMPLEMENTATION`

After implementation, the required sequence remains bounded verification -> repair closeout -> independent rereadiness/rereview -> only then consideration of a fresh one-shot authorization.
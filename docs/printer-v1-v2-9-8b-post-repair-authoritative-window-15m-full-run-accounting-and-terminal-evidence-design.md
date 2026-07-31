# Printer V1 V2-9.8B Post-Repair Authoritative WINDOW_15M Full-Run Accounting and Terminal-Evidence Design

Date: 2026-07-31

Lane:
`V2-9.8B Post-Repair Authoritative WINDOW_15M Full-Run Accounting and Terminal-Evidence Design`

Branch:
`codex/v2-9-8b-full-run-accounting-terminal-evidence-design`

Baseline:
`054865325472416ead6fe68a5f0d2faa734e9b87`

Type: design/specification only.

Verdict:
`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_DESIGN_PASS`

## 0. Boundary

This lane designs the minimum repair for the confirmed factory-to-campaign
ownership and accounting disconnect. It does not implement code, modify a
migration, run a test, contact a source, mutate the authoritative database,
authorize a new attempt, or reinterpret either historical V2-9.8B execution.

The active Printer V1 source stack remains:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The governing lane sequence remains:

```text
audit/readiness -> design/specification -> implementation -> bounded proof/test -> closeout
```

This design does not combine those later stages.

## 1. Confirmed Problem Statement

The forensic closeout at baseline `0548653...` proved that execution
`20260731T145230Z-2f345456ea78` produced two real terminal `WINDOW_15M`
lifecycles:

- window `161`, token `28`, pair `32`, 9/9 snapshots, `WINDOW_CLOSED`;
- window `162`, token `27`, pair `31`, 9/9 snapshots, `WINDOW_CLOSED`.

The factory completed 18 lifecycle steps: 16 snapshot steps and two window-close
steps. Both tokens reached valid post-terminal tracking `COOLDOWN`.

The campaign still remained `BLOCKED_UNSAFE` because the campaign layer could
not prove the full run:

1. windows `161` and `162` were not registered in
   `printer_memory_factory_campaign_windows`;
2. their `printer_memory_windows.cycle_id` values were blank;
3. `printer_memory_factory_campaign_scheduler_work` contained no campaign-owned
   lifecycle Scheduler rows;
4. campaign six-unit evidence contained only pre-lifecycle source stages;
5. Scheduler work, lifecycle reservations, and local validations remained zero
   despite 18 succeeded factory jobs;
6. the lifecycle-started path supplied no independent action-local lifecycle
   surface, and `reconcile_owner_to_action_local` therefore passed vacuously;
7. the canonical campaign report omitted exact per-token/window terminal evidence;
8. unified terminal closure treated still-`SELECTED` campaign slots as
   `MANUAL_REVIEW`, even though the tracking owner had already proved clean
   terminal `COOLDOWN` outcomes.

The root defect is one factory-to-campaign ownership/accounting disconnect. This
design repairs that boundary without introducing a second factory, Scheduler,
source, cleanup, report, or accounting owner.

## 2. Design Goals

The repair must ensure that a future ordinary two-token `WINDOW_15M` campaign can
be accepted only when the campaign layer proves exactly what the factory did.

Required goals:

1. Every real factory memory window has exact campaign, run, cycle, factory-run,
   token, and pair ownership.
2. Every campaign-attributable Scheduler job is exactly owned and reported.
3. Every lifecycle operation contributes once to identity-bearing six-unit
   evidence.
4. The campaign accounting owner and an independent action-local observer prove
   exact equality in both directions.
5. Missing evidence, missing stages, duplicate identities, ownership conflicts,
   and count/identity mismatches fail closed.
6. The canonical terminal report exposes the exact two lifecycle outcomes rather
   than only an aggregate completion label.
7. Campaign PASS remains separate from memory quality. Two dirty or partial but
   honestly terminal windows may satisfy lifecycle completion, but they never
   become clean-memory promotion evidence.
8. `COOLDOWN`, `MANUAL_REVIEW`, and lifecycle completion retain distinct meanings.
9. Replay remains exact-identity, zero-source, zero-Scheduler, and zero-write.
10. All V1 locks remain unchanged.

## 3. Non-Goals

This design does not:

- repair or reclassify historical windows `161` or `162`;
- rewrite historical reports or marker files;
- authorize another live campaign;
- expand beyond two-token `WINDOW_15M`;
- unlock `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or
  PnL;
- introduce scoring, ranking, confidence, weighting, embeddings, or vectors;
- create a second source, Scheduler, terminal, report, or accounting authority;
- turn `WINDOW_5M_MICRO_EVENT` into a main outcome window.

## 4. Ownership Model

One owner remains responsible for each concern.

| Concern | Single owner | Repair responsibility |
| --- | --- | --- |
| Source access | Source Governor | Record every actual source transport through the existing measured transport boundary. |
| Scheduled work | Central Scheduler | Create, claim, complete, fail, and cancel every campaign/factory job. |
| Lifecycle execution | Memory Factory | Execute exact token/pair cadence, snapshots, close, quality gates, and per-token outcomes. |
| Campaign identity | Operational campaign coordinator | Pass and preserve campaign, run, cycle, configuration, supervision, and factory-run identities. |
| Window ownership | Campaign ownership layer | Register each real factory window under the exact campaign/run/cycle identity. |
| Final accounting aggregation | `CampaignSixUnitOwner` | Aggregate sealed stages exactly once and derive totals from durable identities. |
| Independent verification | Action-local observation ledger | Observe operations at execution time without copying owner evidence. |
| Terminal ownership | Unified terminal closure | Terminalize campaign/run/cycle/window/slot ownership and prove zero active residue. |
| Canonical report | Existing campaign report writer | Emit one exact-identity report after accounting and ownership gates pass or block honestly. |

No new owner may directly call a provider, mutate Scheduler state, terminalize
campaign state, or write a competing terminal report.

## 5. Exact Identity Flow

The coordinator already owns:

- `campaign_id`;
- campaign `run_id`;
- `cycle_id`;
- `configuration_id`;
- `supervision_id`;
- `factory_run_id` after factory initialization.

The repair must pass an immutable `OperationalLifecycleOwnershipContext` through
`AuthoritativeLiveOperationalCampaignOwner` -> `OriginToLifecycleCampaignDriver`
-> `run_one_command_15m_factory`.

Required fields:

```text
campaign_id
campaign_run_id
cycle_id
configuration_id
factory_run_id
expected_window_kind = WINDOW_15M
expected_token_capacity = 2
```

The factory may read this context but may not replace any identity. If the
factory-run callback observes a different non-empty factory run ID after initial
binding, the campaign fails closed.

Every lifecycle operation identity must include enough context to prevent
cross-run attribution:

```text
campaign_id
campaign_run_id
cycle_id
factory_run_id
token_id
token_mint
pair_id
pair_address
window_kind
step_id or operation ordinal
```

## 6. Campaign-Window Registration Contract

### 6.1 Existing storage is authoritative

The core repair uses the existing:

- `printer_memory_windows.cycle_id`;
- `printer_memory_factory_campaign_windows`;
- campaign/run/cycle ownership rows;
- campaign-run-to-factory-run linkage.

No replacement window map is introduced.

### 6.2 Registration timing

A real `WINDOW_15M` memory window becomes campaign-owned in the same lifecycle
close transaction in which the window is accepted as the exact result of a
succeeded `WINDOW_CLOSE` step.

Before that transaction is committed, the factory must:

1. verify the close step belongs to the immutable ownership context;
2. verify the window token/pair matches the close step;
3. set `printer_memory_windows.cycle_id` to the exact campaign `cycle_id` for the
   newly created future row;
4. insert the corresponding `printer_memory_factory_campaign_windows` ownership
   row using the exact `campaign_id`, campaign `run_id`, and `window_id`;
5. place the ownership row in the existing canonical terminal state matching the
   closed window;
6. bind the row to the already-authoritative factory run through the existing
   campaign-run/factory-run relationship;
7. verify a read-back identity match before marking the close step succeeded.

Historical rows are never updated by this repair.

### 6.3 Idempotency and conflict behavior

Registration is idempotent only for the exact same identity tuple.

- No row exists: insert once.
- Exact row already exists with matching campaign/run/window/cycle/token/pair:
  return an idempotent success.
- The window is already owned by another campaign/run/cycle, or the ownership row
  points at a different token/pair: fail closed with
  `CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT`.
- A window exists but `cycle_id` is blank or mismatched in a new run: fail closed;
  do not repair it after commit.
- A close step succeeds without a verified ownership row: the factory run cannot
  report `COMPLETED` and the campaign cannot write a PASS-eligible report.

### 6.4 Terminal reconciliation

Unified terminal closure continues to read
`printer_memory_factory_campaign_windows`.

For a normally closed window, it reports an already-terminal owned window rather
than an empty map. For an active owned window during a failure, it transitions the
existing ownership row through the existing state owner. It never invents a
window from aggregate factory status.

## 7. Campaign Scheduler Ownership

Every campaign-attributable Scheduler job must have one durable ownership path.

The repair uses the existing campaign Scheduler ownership table and existing
factory run-step linkage rather than introducing a new Scheduler table.

Required job families:

1. discovery and selection Scheduler jobs;
2. executor first-15m handoff jobs;
3. factory opening snapshot jobs;
4. anchored snapshot jobs;
5. factory window-close jobs;
6. terminal cleanup cancellations, where a still-active owned job exists.

For each job, persist or prove:

```text
scheduler_job_id
campaign_id
campaign_run_id
cycle_id
factory_run_id when applicable
stage_id
job_kind
token/pair identity when applicable
terminal status
```

One job ID may appear in only one accounting stage. Existing immutable selected
item links remain the ownership source for executor first-15m jobs. Factory
run-step rows remain the ownership source for lifecycle jobs. The campaign
Scheduler ownership projection must reference those canonical IDs rather than
creating replacement jobs.

## 8. Full-Run Six-Unit Stage Model

### 8.1 Evidence version

Future repaired operational runs use identity-bearing
`CAMPAIGN_SIX_UNIT_EVIDENCE_V2`.

Historical V1 evidence remains readable and replayable as historical evidence but
is never upgraded or treated as proof of a repaired full run.

The V2 evidence payload remains JSON and therefore requires no database schema
migration by itself.

### 8.2 Six units

Every stage derives the same six totals:

```text
SOURCE_TRANSPORT_OPERATION
NORMALIZED_SOURCE_ROWS
SOURCE_RESPONSE_BYTES
SCHEDULER_WORK_ITEM
LIFECYCLE_RESERVED_TRANSPORT_OPERATION
LOCAL_VALIDATION_STEP
```

Transport totals continue to derive from exact measured transport identities.
The three non-transport units become identity-bearing rather than count-only.

Required identity records:

- Scheduler work item:
  `stage_id + scheduler_job_id + job_kind + target identity`;
- lifecycle reservation:
  `stage_id + factory_run_id + token/pair + window kind + reservation ordinal`;
- local validation:
  `stage_id + factory step or window identity + validation kind + validation ordinal`.

Totals are derived from unique identity sets. Callers may not submit an arbitrary
integer without the identities that produce it.

### 8.3 Required stage manifest

The campaign owner maintains one expected-stage manifest.

Pre-lifecycle source stages already used by the ordinary campaign remain, with
stable deterministic IDs and sequences.

After atomic two-slot activation, the following additional stages become
mandatory:

1. `DISCOVERY_SELECTION_SCHEDULER`
   - campaign-owned discovery/selection Scheduler jobs;
   - handoff validation operations;
   - no lifecycle transport reservation.

2. `WINDOW_15M_SLOT_1`
   - exact slot-1 token/pair;
   - opening and anchored snapshot jobs;
   - snapshot and context transports;
   - lifecycle transport reservations;
   - cadence, identity, budget, close, coverage, and quality validations;
   - exact terminal window ID.

3. `WINDOW_15M_SLOT_2`
   - same contract for the second distinct token/pair.

4. `CAMPAIGN_TERMINAL_RECONCILIATION`
   - final ownership reconciliation validations;
   - exact active-job cancellations, if any;
   - zero-active-work and forbidden-delta validations;
   - no duplicated lifecycle job or transport identities.

A stage is sealed once with a deterministic stage ID containing campaign, run,
cycle, stage kind, and sequence. Started stages may terminalize as `COMPLETED`,
`BLOCKED`, or `FAILED`, but none may disappear from the manifest.

### 8.4 Stage completion law

A stage is complete only when:

- it has exact ownership identities;
- all started operations are terminal;
- its durable operation identities reconstruct its totals;
- no operation identity appears in another stage;
- its first terminal cause is preserved;
- the campaign owner ingests it exactly once.

A lifecycle-started run with either slot stage absent or unsealed is
`BLOCKED_UNSAFE`.

## 9. Independent Action-Local Measurement

### 9.1 Separate ledger

The coordinator creates a separate `CampaignActionLocalLedger` before operational
work starts. It is verification-only and never becomes the accounting owner.

It observes operations directly at their execution boundaries:

- measured source transport observer;
- Scheduler enqueue/claim/terminal observer;
- lifecycle reservation observer when cadence capacity is reserved;
- local validation observer when a named validation actually executes.

The action-local ledger must not be built by copying sealed stage evidence or by
querying the final report.

### 9.2 Required observer propagation

The coordinator passes observer callbacks through the same immutable lifecycle
context into the factory. Operational persistent mode requires all observer
families. Fixture/proof modes may inject deterministic observers, but a repaired
operational run cannot silently omit them.

### 9.3 Equality contract

Final reconciliation compares owner and action-local evidence for all six units:

- exact transport identity sets;
- normalized-row and byte totals derived from matching transports;
- exact Scheduler job identity sets;
- exact lifecycle reservation identity sets;
- exact local validation identity sets;
- exact derived totals.

Equality is bidirectional:

- owner-only identity: block;
- action-local-only identity: block;
- equal counts with different identities: block;
- missing action-local surface: block;
- empty lifecycle surface after `lifecycle_started=true`: block;
- duplicate identity: block.

The current vacuous behavior is forbidden. `reconcile_owner_to_action_local`
must accept an explicit repaired operational mode requiring non-empty action-local
surfaces. Absence returns `ACTION_LOCAL_LIFECYCLE_EVIDENCE_MISSING`, never
`equal=true`.

## 10. Canonical Terminal Report Contract

The canonical report remains one exact-identity report. It adds a full-run
terminal-evidence section derived from durable DB rows and sealed accounting
identities.

Required fields:

### 10.1 Identity and ownership

- execution ID;
- campaign ID;
- campaign run ID;
- cycle ID;
- configuration ID;
- supervision ID;
- factory run ID;
- exact launch Git provenance;
- exact database target identity.

### 10.2 Selection and lifecycle

- exactly two selected token/pair identities, or an honest pre-lifecycle shortage;
- exact selection batch and token-slot identities;
- per-token factory step IDs and Scheduler job IDs;
- exact window IDs;
- campaign-window ownership rows;
- snapshot IDs and expected/actual/missing counts;
- coverage status;
- window status;
- memory status, quality label, data quality, and `do_not_train`;
- episode identity, if lawfully created;
- per-token terminal outcome and tracking disposition.

### 10.3 Full-run accounting

- expected-stage manifest;
- sealed stage IDs and terminal statuses;
- six identity-bearing unit sets or their canonical durable hashes;
- derived six-unit totals;
- owner/action-local exact equality result for every unit;
- Scheduler attribution split by discovery, handoff, lifecycle, and cleanup;
- explicit missing/unsealed/mismatched evidence list.

### 10.4 Terminal safety

- campaign/run/cycle/supervision/factory terminal state;
- campaign-window reconciliation result;
- zero active and locked work;
- lease release;
- zero forbidden deltas;
- no retry, restart, resume, or successor;
- marker and artifact hashes.

### 10.5 Acceptance verdict

The report distinguishes:

```text
runtime_terminal_status
campaign_acceptance_verdict
memory_quality_outcomes
```

A runtime may terminalize cleanly while campaign acceptance is blocked. A memory
may be partial or dirty while lifecycle completion is valid. These are never
collapsed into one `COMPLETED` label.

## 11. Campaign Acceptance Gate

Campaign PASS requires every condition below:

1. exactly one authorized invocation;
2. exactly two distinct selected token/pair identities;
3. exactly two succeeded terminal `WINDOW_CLOSE` steps;
4. exactly two real `WINDOW_15M` rows with complete cadence evidence;
5. both windows carry the exact campaign cycle ID;
6. both windows have exact campaign-window ownership rows;
7. all required stages exist and are sealed;
8. all six unit identity sets reconcile exactly owner-to-action-local;
9. all attributable Scheduler jobs are terminal and owned;
10. canonical report contains exact per-token/window evidence;
11. exact-identity replay reproduces the report with zero source, Scheduler, and
    write activity;
12. terminal cleanup and forbidden-delta checks pass.

Memory quality does not lower this gate. `PARTIAL_MEMORY`, `DIRTY_MEMORY`, or
`DO_NOT_TRAIN` may be reported honestly after real lifecycle completion, but they
cannot be promoted as clean memory.

Outcome mapping:

- complete pre-lifecycle shortage with trustworthy evidence: `HONEST_BLOCKED`;
- lifecycle started but ownership/accounting/report evidence missing or
  mismatched: `BLOCKED_UNSAFE`;
- all acceptance gates satisfied: Campaign PASS.

## 12. COOLDOWN, MANUAL_REVIEW, and Slot Semantics

The tracking queue and campaign token slot represent different ownership layers.

- Tracking `COOLDOWN` means the token reached a valid terminal main-window outcome
  and entered the configured re-track delay.
- Slot `MANUAL_REVIEW` means lifecycle ownership could not prove a valid terminal
  main-window outcome for that slot.
- Slot `COOLDOWN` means the campaign ownership layer proved a terminal main-window
  outcome and mirrored the lawful post-cycle disposition.

Unified terminal closure remains the sole campaign-slot terminal authority.

Required behavior:

1. If no lifecycle started, remaining `SELECTED` slots may become
   `MANUAL_REVIEW`.
2. If a campaign-owned terminal window exists for a slot and the post-cycle queue
   disposition is `COOLDOWN`, unified closure transitions that slot to
   `COOLDOWN`, not `MANUAL_REVIEW`.
3. If lifecycle started but no valid owned terminal window exists, the slot
   becomes `MANUAL_REVIEW` or `FAILED` according to the preserved first terminal
   cause, and the campaign is not PASS-eligible.
4. The queue owner continues to own tracking status. Unified closure does not
   rewrite a valid queue `COOLDOWN` into a pre-lifecycle failure label.

## 13. Quality-Label Consistency

Historical windows and episodes remain immutable.

For future repaired runs:

- `WINDOW_15M_CLEAN_MEMORY` episode creation is allowed only when the source window
  is `CLEAN_MEMORY`, carries clean quality/data labels, and `do_not_train=0`;
- a `PARTIAL_MEMORY`, `DIRTY_MEMORY`, `AUDIT_ONLY_MEMORY`, or `DO_NOT_TRAIN`
  window cannot produce a clean-memory episode kind;
- if the existing episode schema has no lawful partial/dirty episode kind, the
  factory creates no promotable episode for that window and records an explicit
  `NO_CLEAN_EPISODE_CREATED` outcome;
- lifecycle completion remains valid when the window is partial or dirty;
- clean-memory promotion and retrieval eligibility remain separately locked.

The canonical report must expose a `quality_consistency` result. An inconsistency
blocks clean-memory acceptance but does not erase the real lifecycle outcome.

## 14. Schema and Migration Decision

### 14.1 Core decision

No new migration is required for the core repair because the repository already
contains:

- `printer_memory_windows.cycle_id`;
- `printer_memory_factory_campaign_windows`;
- `printer_memory_factory_campaign_scheduler_work`;
- campaign/run/cycle/factory-run linkage;
- JSON report and six-unit evidence surfaces.

The implementation lane must perform a static schema verification before code
changes. It must confirm that the existing campaign-window and campaign-Scheduler
ownership tables can enforce one exact ownership row per canonical ID.

### 14.2 Stop condition

If static inspection proves that the existing schema lacks a necessary unique or
foreign-key constraint that cannot be enforced safely through an existing primary
key, implementation must stop and return a narrow design amendment for a
migration. It must not add an opportunistic migration inside the implementation
lane.

Historical rows receive no backfill migration.

## 15. Failure, Rollback, and Terminalization

### 15.1 Window-close transaction failure

If a memory window is created but campaign ownership cannot be registered before
commit, the close step fails and the transaction rolls back. No unowned committed
future window is accepted.

If an underlying close owner commits before registration and cannot be made
atomic, implementation must introduce an explicit compensation boundary before
using the path operationally. The campaign then terminalizes `BLOCKED_UNSAFE` and
cannot report PASS.

### 15.2 Accounting failure

Any malformed, missing, duplicate, unsealed, or mismatched stage blocks report
acceptance. The coordinator preserves the first terminal cause, terminalizes
owned work, and writes an honest blocked terminal summary. It does not fabricate
missing operation identities from row counts.

### 15.3 Idempotent terminal closure

Repeated terminal reconciliation over the same terminal graph:

- creates no new window ownership;
- creates no new Scheduler ownership;
- changes no first terminal cause;
- creates no duplicate stage evidence;
- leaves zero active work;
- returns the same terminal ownership projection.

### 15.4 Replay

`report-only` accepts exact campaign/run identities only. Replay:

- reads the stored report and durable evidence;
- independently reconstructs full-run ownership and six-unit totals from existing
  rows/evidence;
- compares exact identities and canonical bytes;
- performs no source call, Scheduler action, or DB write;
- cannot select a historical report by fallback.

## 16. Implementation Slices

Implementation must proceed in this order after design operator review.

### Slice 1 - Ownership context and schema readiness

- verify existing schema constraints;
- add immutable lifecycle ownership context plumbing;
- add focused identity-drift tests.

### Slice 2 - Campaign-window and campaign-Scheduler ownership

- register future windows and cycle IDs atomically;
- project exact existing Scheduler job IDs into campaign ownership;
- add idempotency and conflict tests.

### Slice 3 - Identity-bearing lifecycle accounting

- introduce V2 non-transport identity records;
- seal discovery Scheduler, slot-1, slot-2, and terminal stages;
- prevent duplicate cross-stage identities.

### Slice 4 - Independent action-local lifecycle observation

- propagate transport, Scheduler, reservation, and validation observers;
- make absent lifecycle action-local evidence fail closed;
- prove bidirectional exact equality and mismatch cases.

### Slice 5 - Canonical report and acceptance gate

- add full-run identities and outcomes;
- separate runtime terminal, campaign acceptance, and memory quality;
- block PASS unless every gate is proven.

### Slice 6 - Terminal slot and quality semantics

- transition campaign slots according to proven lifecycle ownership;
- preserve queue `COOLDOWN` meaning;
- block clean episode creation from non-clean windows.

No slice unlocks another live attempt.

## 17. Minimum Disposable Proof Plan

The later proof lane uses a disposable database only and requests the minimum
sufficient tests for this architectural change.

### 17.1 Positive two-token proof

Prove one deterministic campaign with:

- two distinct selected token/pair identities;
- 16 snapshot steps and two close steps;
- 18 exact lifecycle Scheduler jobs;
- two terminal `WINDOW_15M` rows;
- exact cycle IDs;
- two campaign-window ownership rows;
- complete campaign Scheduler ownership;
- complete required-stage manifest;
- non-empty action-local identities for all required units;
- exact owner/action-local equality;
- complete canonical terminal report;
- exact zero-side-effect replay;
- zero active residue and zero forbidden deltas.

### 17.2 Required negative proofs

1. Missing campaign-window registration -> `BLOCKED_UNSAFE`.
2. Window ownership conflict -> fail closed and no PASS report.
3. Missing slot lifecycle stage -> `BLOCKED_UNSAFE`.
4. Missing action-local lifecycle surface ->
   `ACTION_LOCAL_LIFECYCLE_EVIDENCE_MISSING`.
5. Equal counts with different identities -> reconciliation mismatch.
6. Duplicate operation identity across stages -> accounting block.
7. Missing Scheduler ownership row -> accounting/report block.
8. Partial or dirty terminal windows -> lifecycle completion may pass, clean
   promotion remains blocked.
9. Clean episode label attached to non-clean window -> quality-consistency block.
10. Failure after first window -> terminal closure owns/cancels only exact scoped
    work and leaves zero active residue.
11. Repeated registration/closure/replay -> idempotent, no duplicate rows.
12. Historical V1 report replay remains historical and is never upgraded to V2
    PASS evidence.

### 17.3 Verification scope

Use focused unit/integration tests and one bounded disposable end-to-end proof.
Do not request a broad repository regression suite until implementation closeout
or another checkpoint justifies it. Unrelated pre-existing failures must be
recorded without expanding scope automatically.

## 18. Money-Usefulness Contribution

This repair is defensive money-usefulness. Printer cannot learn safely from a
window merely because the factory produced it; the campaign must prove who owned
it, which operations created it, whether those operations reconcile, and what the
actual terminal quality was.

The design improves future money-usefulness by:

- preventing false PASS terminals from entering operational history;
- making two-token learning runs auditable by exact identity;
- ensuring partial/dirty outcomes teach risk without being promoted as clean;
- preserving capital-protection lessons while retrieval and decisions remain
  locked;
- reducing the chance that later paper decisions are built on unverifiable
  memory-growth evidence.

It makes no profit claim and creates no trading capability.

## 19. What This Design Improves

- closes the factory-to-campaign window ownership gap;
- closes the campaign Scheduler ownership gap;
- extends six-unit accounting through the real lifecycle;
- replaces vacuous reconciliation with exact non-empty equality;
- makes the terminal report show the real two-token/window outcomes;
- separates runtime completion, campaign acceptance, and memory quality;
- preserves valid `COOLDOWN` semantics;
- prevents clean episode labels from contradicting non-clean windows.

## 20. What Remains Locked

This design does not unlock:

- implementation;
- a live campaign or rerun;
- clean-memory promotion of historical windows `161`/`162`;
- `WINDOW_1H` or later windows;
- retrieval;
- paper decisions;
- BUY, SELL, or HOLD;
- positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk or blocker | Why it matters | Required mitigation | Proof needed |
| --- | --- | --- | --- |
| Window close commits before ownership registration | Can create another real but campaign-orphaned window | Make registration part of the close transaction or add explicit fail-closed compensation before operational use | Fault at every close/registration boundary |
| Non-transport units remain count-only | Equal totals can hide different Scheduler or validation work | Identity-bearing Scheduler/reservation/validation records | Equal-count/different-ID tests |
| Action-local ledger is derived from owner evidence | Creates another self-comparison | Observe independently at execution boundaries | Deliberate owner/action-local divergence |
| Duplicate operation ownership | Inflates totals and weakens budget truth | Stable identity keys and cross-stage duplicate rejection | Duplicate stage/operation tests |
| Terminal owner and post-cycle reconciler conflict | Can produce COOLDOWN and MANUAL_REVIEW simultaneously | Keep queue status with tracking owner and campaign slot terminalization with unified closure | Terminal slot/queue matrix tests |
| Quality labels remain inconsistent | Can create false clean episodes | Gate clean episode creation on exact window quality | Partial-window quality test |
| Existing ownership schema lacks a necessary constraint | Code-only idempotency may race | Static schema readiness gate; stop for design amendment if necessary | Schema/constraint inspection |
| Repair grows into a broad architecture rewrite | Increases regression and proof cost | Keep slices limited to ownership, accounting, report, and terminal semantics | Focused diff and test-scope review |
| One authorized live attempt was consumed | No immediate live retry is permitted | Complete implementation, disposable proof, and closeout before fresh readiness | Lane closeout and new authorization sequence |

## 21. Acceptance of This Design

This design passes when operator review confirms that it:

- addresses the confirmed root cause without adding competing owners;
- specifies exact campaign-window and Scheduler ownership;
- specifies identity-bearing full-run six-unit evidence;
- requires independent non-empty action-local equality;
- defines fail-closed terminal/report behavior;
- preserves all Printer V1 locks;
- keeps implementation and proof in later lanes.

Verdict:

`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_DESIGN_PASS`

## 22. Exact Next Permitted Lane

After operator review and integration of this design:

```text
V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Implementation
```

That lane may implement only the approved slices above. It may use focused tests
and disposable databases, but it may not run another live campaign, mutate or
reclassify historical execution rows, merge the historical final-authorization
branch, or unlock retrieval or financial capabilities.

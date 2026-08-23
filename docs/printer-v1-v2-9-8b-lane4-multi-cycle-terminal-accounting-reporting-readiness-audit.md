# Printer V1 V2-9.8B Lane 4 Multi-Cycle Terminal Accounting / Reporting Readiness Audit

Date: 2026-08-23

Lane: `V2-9.8B Lane 4 — Multi-Cycle Terminal Accounting / Reporting`

Scope: audit/readiness only; Cycle 1 and Cycle 2 only

Starting HEAD: `e70b2faf4906f73faec2adf9321d04385e362e81`

Verdict:

`V2_9_8B_LANE4_MULTI_CYCLE_TERMINAL_ACCOUNTING_REPORTING_READINESS_AUDIT_PASS_READY_FOR_DESIGN`

This PASS means the current production path and its design inputs are sufficiently
resolved for a separate design/specification task. It is not a runtime PASS, does
not repair the defects below, and does not authorize a campaign, retry, restart,
successor, report regeneration, or Cycle 3.

## 1. Audit basis and boundary

The audit read the required authority stack, current handoff, Lane-3 closeout and
only the Lane-3 readiness/design material needed to preserve its contracts. It
then traced the current operational command, campaign/cycle coordinator, factory,
Scheduler ownership, Standard-4H progression, campaign accounting, terminal
closure, report writer, terminal-summary writer, schemas, and focused test-only
adapters.

No provider was contacted. No Printer command, campaign, report replay, test, or
database mutation was run. No production code, test, schema, migration, or config
was changed. Historical evidence was not treated as proof of the post-Lane-3
combined path.

## 2. Exact current production path

```text
run_four_token_standard_four_hour_campaign
  -> _run_operational_campaign
  -> AuthoritativeLiveOperationalCampaignOwner.run_operational
  -> run_one_command_15m_factory
  -> Cycle 1 durable ownership graph + Scheduler-led lifecycle
  -> Lane-3 Standard-4H progression attempt/tokens for Cycle 1
  -> governed Cycle-2 acquisition/admission
  -> Cycle 2 durable ownership graph + Scheduler-led lifecycle
  -> Lane-3 Standard-4H progression attempt/tokens for Cycle 2
  -> reconcile_four_token_cycle_terminal for each admitted cycle
  -> finalize_four_token_shared_terminal
  -> cleanup_campaign_supervision + reconcile_campaign_terminal
  -> assemble_campaign_terminal_reporting
  -> finalize_full_run_ownership_and_report
  -> build_campaign_terminal_report
  -> write_campaign_terminal_report
  -> terminal-summary.json
```

Production entry and composition are real. Despite retained `proof` names,
`build_operational_multi_cycle_controller()` is used by the authorized operational
four-token command. Cycle 2 is admitted by
`multi_cycle_campaign_coordinator.admit_two_token_cycle_from_attempt`; it is not a
fixture-only cycle.

### Transition ownership map

| Transition | Producer / owner | Persisted authority and exact identity | Consumer | Success / fail-closed meaning |
|---|---|---|---|---|
| Campaign -> run | operational command and campaign persistence | campaign row; `campaign_runs(run_id,campaign_id,run_state,first_terminal_cause)` | supervision, factory, terminal closure | one exact campaign/run; missing or conflicting ownership blocks |
| Run -> Cycle 1 | initial admission | `campaign_cycles(cycle_id,campaign_id,run_id,cycle_ordinal=1)` | factory and Scheduler ownership | exact ordinal 1 graph |
| Cycle 1 -> slots | atomic two-slot handoff | slots keyed by `token_slot_id`; exact campaign/run/cycle, ordinal, token/mint/pair, queue and lifecycle | window planning, Scheduler, progression | exactly two distinct slots or fail closed |
| Slot -> windows/work | factory plus campaign-ownership owner | campaign windows and stage-scoped campaign work carrying campaign/run/cycle/slot/window/job/factory-run identity | claimed-job owner, close owner, accounting | exact owner resolution; missing/mismatched mirror is not success |
| 1h -> 4h | Lane-3 progression owner | one progression attempt per campaign/run/cycle and two progression-token rows, including exact predecessor/successor identities and fault envelope | shared Lane-3 derivation, 4h planner, accounting validator | 0/1/2 handoff; missing or partial aggregate derives interrupted/ambiguous |
| Cycle 1 -> Cycle 2 | multi-cycle controller and pre-admission owner | exact proposed ordinal 2 attempt, then a new `cycle_id` and two new cycle-scoped slots | Cycle-2 lifecycle | admission is atomic; no reuse of Cycle-1 slots |
| Per-cycle terminalization | `reconcile_four_token_cycle_terminal` | terminal cycle/slot/window/work rows and Scheduler state | shared terminalizer | currently validates shape/zero active work but does not derive the cycle result from canonical per-cycle outcomes |
| Shared terminalization | `finalize_four_token_shared_terminal` -> supervision cleanup and `reconcile_campaign_terminal` | campaign/run terminal rows, immutable first cause, cleanup/lease state | accounting and reporting | requires terminal admitted-cycle prefix and zero active work; does not prove each cycle's semantic result |
| Full-run accounting | `finalize_full_run_ownership_and_report` | read-side projection from durable rows plus in-memory six-unit owners/action-local ledger | campaign acceptance and embedded evidence | fail-closed; currently scoped to initial Cycle 1 while reading factory-run-wide steps |
| Final report | `build_campaign_terminal_report` + `write_campaign_terminal_report` | one immutable report row and one canonical JSON artifact | report-only and operator | identical replay is idempotent; divergent payload fails |
| Terminal summary | operational command | `terminal-summary.json` under execution artifact root | report-only fallback/operator | adapted, separately written surface; not runtime authority |

## 3. Canonical per-cycle terminal owners

No single reporting label is sufficient. The canonical per-cycle result is a
composite of the following persisted production owners:

1. `printer_memory_factory_campaign_cycles` owns cycle identity and the broad
   `TERMINAL_*` state plus immutable `first_terminal_cause`.
2. `printer_memory_factory_campaign_token_slots` owns token-local disposition.
3. `printer_memory_factory_campaign_windows` owns exact 15m/1h/4h window state
   and memory-row linkage. `DIRTY` and `NO_PROMOTION` can be honest terminal
   non-CLEAN outcomes; they are not automatically execution failure.
4. `printer_memory_factory_campaign_scheduler_work`, the referenced Scheduler
   job, and the exact factory step own work execution truth.
5. Lane-3 progression attempts/tokens plus
   `derive_standard_4h_progression_status()` own post-1h/4h progression truth.
6. Supervision lease/cleanup and active-work queries establish whether apparently
   unfinished state is live or interrupted.

### Exact semantic map for either Cycle 1 or Cycle 2

| Requested meaning | Authoritative persisted meaning |
|---|---|
| Completed successfully | `cycle_state=TERMINAL_COMPLETED` is necessary, not sufficient. Exact two-slot identity, required terminal 15m/1h outcomes, Lane-3 progression `complete=true`, every required eligible 4h successor terminal, exact Scheduler/work correspondence, and zero active ownership must agree. Honest non-CLEAN memory remains reportable without becoming CLEAN. |
| Failed | A canonical token/progression/window/work/Scheduler failure establishes the locus. `cycle_state=TERMINAL_FAILED` should agree, but current Phase-A terminalization does not prove that agreement. |
| Cancelled | Cancellation is exact in progression (`TERMINAL_CANCELLED`), window/work/Scheduler `CANCELLED`, and stop/cancellation cause. The cycle table has no `TERMINAL_CANCELLED`; its broad row resolves to `TERMINAL_STOPPED` or `TERMINAL_BLOCKED` according to status/cause. Lower-level cancellation truth therefore remains required. |
| Interrupted / ambiguous | Lane-3 derivation returns `INTERRUPTED_AMBIGUOUS` for missing progression, stopped waiting/evaluating state, partial successor graphs, missing Scheduler/work mirrors, or inactive unfinished ownership. The cycle table has no distinct interrupted enum. Active rows with a live exact owner remain active/incomplete; the same rows without live ownership require review. |

The same rules apply independently to both cycle IDs. Cycle ordinal is not a
substitute for `cycle_id`.

## 4. Cycle-1 / Cycle-2 identity and isolation audit

### Correctly cycle-scoped production ownership

- Campaign cycles are unique by `(run_id, cycle_ordinal)` and exact by
  `(cycle_id,run_id,campaign_id)`.
- Slots are unique by `(cycle_id,slot_ordinal)` and `(cycle_id,token_row_id)`.
- Windows and work carry campaign/run/cycle/slot/window identities through
  composite foreign keys.
- Migration 050 stage-scoped work binds the Scheduler job to its exact cycle,
  slot, window, stage, target, and factory run.
- Claimed factory jobs call `resolve_owned_cycle_for_scheduler_job`; Cycle-2 work
  is not executed using the initial lifecycle context.
- Lane-3 progression is unique per campaign/run/cycle and carries exact slot,
  token, mint, pair, queue, lane, predecessor, successor, factory run, and
  configuration identity.
- Cycle-2 admission creates new slots and checks disjoint token/pair identity.

These constraints prevent Cycle-2 terminalization from rewriting an already
terminal Cycle-1 ownership row. Terminal transitions and first causes are
immutable. A failed Cycle 1 also cannot create or rewrite Cycle 2; Cycle 2 exists
only after its separate admission owner commits it.

### Present isolation failures at campaign end

1. `run_one_command_15m_factory` derives one `cycle_run_status` from the global
   stop reason, attempt cause, and admitted-cycle count, then passes the same
   status and cause to every admitted cycle. The per-cycle terminalizer checks
   two slots and canonical work shape, cancels remaining work, and writes the
   supplied terminal result. It does not consume the already-available
   cycle-scoped window/progression derivation. A cycle-local failure, cancellation,
   interruption, or honest token-local result can therefore be flattened into a
   shared label. Classification: `PROVEN_CODE_DEFECT`.

2. Full-run accounting selects close steps and lifecycle jobs for the entire
   `factory_run_id`, but resolves every token slot, campaign window, Scheduler
   mirror, report window, and report work row through the single
   `context.cycle_id`. The operational caller supplies the initial Cycle-1 ID.
   Cycle-2 close steps consequently reach `NO_CAMPAIGN_SLOT_FOR_TOKEN:*`; its jobs
   reach `SCHEDULER_PROJECTION_WITHOUT_WINDOW:*`; its canonical rows are excluded
   from the embedded full-run report. Classification: `PROVEN_CODE_DEFECT`.

These defects fail closed at campaign acceptance; no path from them to a truthful
multi-cycle PASS was found. They nevertheless prevent correct terminal
accounting/reporting of the approved two-cycle runtime.

Accordingly, a successful Cycle 1 cannot by itself produce campaign acceptance
PASS while Cycle 2 is failed or incomplete, but the current shared cycle/report
labels can mask which cycle supplied the failure. A failed Cycle 1 can cause the
same shared terminal cause to be written to a still-nonterminal Cycle 2 even when
Cycle 2's local facts differ. A terminal Cycle-1 row cannot be rewritten by
Cycle-2 terminalization.

## 5. Token-local, cycle-level, and campaign-level fault hierarchy

The existing production facts support this hierarchy, even though the current
campaign-end consumers do not preserve it fully:

| Scope | Canonical examples | Required propagation |
|---|---|---|
| Token-local honest non-CLEAN | terminal `DIRTY`, `NO_PROMOTION`, or ineligible progression with exact evidence | report at token/cycle scope; never call CLEAN; does not alone fail campaign |
| Token-local failure | exact token progression `TERMINAL_FAILED`, failed window/work/job tied to one slot | keep token cause; cycle policy decides shared effect |
| Token-local cancellation/interruption | exact cancelled rows or Lane-3 ambiguous derivation for one slot | preserve token scope; do not manufacture shared failure |
| Cycle-shared failure | admission integrity, missing two-slot ownership, cycle-wide Scheduler/progression integrity | fail that cycle and retain affected token evidence |
| Campaign-shared failure | supervision/lease, DB integrity, accounting ownership, forbidden capability delta, shared cleanup | fail/block campaign; do not hide behind a token label |
| Later closure/report fault | cleanup, accounting, artifact persistence, summary write | secondary evidence unless it is the first exact campaign fault |

The current terminal report exposes one shared terminal cause and a generic
`fault_details` projection. It does not emit this hierarchy per cycle. That
reporting omission is `BASELINE_ACCOUNTING_REPORTING_DEBT`.

## 6. Cycle-2 ownership audit

Cycle 2 has a real production producer and consumer:

1. Later-cycle governed supply is requested with ordinal 2 and a cycle-qualified
   execution identity.
2. The pre-admission attempt persists proposed campaign/run/factory/ordinal and
   exact selected-pair evidence.
3. The coordinator atomically creates the ordinal-2 cycle and two new slots.
4. The factory materializes exact 15m ownership and Scheduler jobs for those
   slots.
5. Job claims resolve the job's owned cycle before lifecycle processing.
6. Standard 1h and Lane-3 4h progression use that resolved `cycle_id`.
7. Cycle terminalization receives the admitted Cycle-2 ID.

No present Cycle-1 slot reuse, fixed token ID, or fixed Scheduler-job assumption
was found in admission or execution. The fixed-Cycle-1 assumptions begin at the
full-run accounting/report boundary described above.

## 7. Full-run accounting audit

`finalize_full_run_ownership_and_report()` is the current campaign-acceptance
owner. It reads durable close steps, memory rows, campaign ownership, Scheduler
jobs/work, invocation authority, cleanup/lease evidence, and forbidden deltas;
then reconciles the six-unit owner with the action-local ledger and applies the
campaign gate.

The operational command correctly registers separate Cycle-1 and Cycle-2
six-unit owners and can create a `CampaignSixUnitProjection`. That projection
aggregates evidence but deliberately retains the primary Cycle-1 owner identity.
The downstream context also remains Cycle 1. Aggregated evidence therefore does
not repair read-side cycle identity.

The current gate does not silently equate missing rows, absent manifests,
`HANDOFF_COMMITTED`, a single successful cycle, or report creation with campaign
success. Missing/mismatched state produces block reasons and prevents PASS.
However, it cannot currently compute a correct two-cycle result because of the
Cycle-1 scoping defect.

There is no canonical persisted `PARTIALLY_COMPLETE` campaign state. The truthful
state must be derived from the two required cycle composites:

- both complete and zero active work: complete candidate;
- one complete and the other active with live ownership: still active/incomplete;
- one complete and the other unfinished without live ownership: interrupted/
  ambiguous;
- any cycle-shared or campaign-shared failure: failed/blocked according to the
  exact cause;
- exact operator cancellation: stopped/cancelled, not generic success.

The campaign/run terminal rows are the broad runtime authority. Full-run
accounting is the acceptance/evidence owner, not permission to rewrite those
rows. Report persistence is not terminal runtime truth.

## 8. Terminal-report audit

The active success/failure producer is
`unified_terminal_closure.build_campaign_terminal_report()` followed by
`write_campaign_terminal_report()`. The current operational path does not use
the broader `final_campaign_report.assemble_final_campaign_report()` as its
canonical producer.

The persisted report has exact campaign, configuration, run, initial cycle,
factory run, report, and execution identity. It embeds:

- shared terminal status/cause;
- cleanup/reconciliation;
- aggregate six-unit evidence;
- selective-1h projection;
- the full-run accounting report and campaign-acceptance result;
- clean-memory outcome and permanent locks.

It does not contain a canonical array of admitted cycles. It cannot independently
show, for each cycle, admission/active/waiting/terminal status, token outcomes,
15m/1h/4h outcomes, Lane-3 progression, Scheduler/work state, primary/secondary
faults, cancellation, or interruption. The embedded full-run report is itself
Cycle-1 scoped. A final operator therefore cannot distinguish every requested
per-cycle state or reliably distinguish “one cycle complete, second incomplete”
from a shared terminal label. Classification: `PROVEN_CODE_DEFECT` because this
is the real report producer for the currently approved two-cycle shape.

Report persistence itself is strong: one report ID maps to one immutable row and
one canonical artifact; identical replay is idempotent, while a differing payload
fails. The report writer performs no source or Scheduler work.

## 9. Terminal-summary audit

The terminal summary is constructed separately after report persistence and
written with `Path.write_text()` to `terminal-summary.json`. It embeds the report
and campaign acceptance but has only the initial Cycle-1 child projection. It has
no per-cycle list, counts, progression hierarchy, or independent derivation of
active/incomplete Cycle 2.

The report-only fallback `_load_exact_terminal_summary()` requires exact
`campaign_id`, `run_id`, `configuration_id`, and `execution_id`. Every inspected
current summary producer omits top-level `configuration_id`. Therefore a real
summary cannot satisfy its own production reader when the report row is absent.
Classification: `PROVEN_CODE_DEFECT`.

The summary file also lacks the report writer's create-once/differing-payload
guard and atomic fsync/replace contract. It can be absent after a durable report,
or overwritten independently. Classification:
`BASELINE_ACCOUNTING_REPORTING_DEBT`.

When report and summary differ, authority order is:

1. canonical runtime rows and supervision/cleanup state;
2. immutable campaign report row plus matching canonical artifact;
3. terminal summary as an adapted convenience surface only.

The summary never overrides runtime or report truth.

## 10. First-cause preservation across cycles

### Proven preservation

- Campaign, run, cycle, slot, window, and work terminal transitions preserve an
  existing terminal row and its first cause.
- Lane-3 progression attempt/token identity, terminal state, primary fault, and
  committed 1h predecessor truth are immutable; later faults append as secondary.
- `_primary_terminal_cause()` scans real failed factory steps and source-failure
  rows before falling back to a generic loop stop.
- Post-report integrity records later cleanup/DB-delta details as secondary and
  only changes a formerly completed status when safety requires it.
- Failure terminalization reads an existing campaign/supervision first cause
  before using the newly caught exception. A later report or cleanup exception
  was not found rewriting a committed campaign first cause.

### Present loss of scope, not loss of lower-level evidence

Phase A supplies the same campaign-level cause to every newly terminalized cycle.
The terminal report then emits that shared cause instead of reading each cycle's
canonical progression/window/work primary and secondary faults. Later
cycle-specific causes survive in their lower-level rows, but they are not
reconciled into the operator report. Classification:
`BASELINE_ACCOUNTING_REPORTING_DEBT`.

No missing historical cause should be guessed or backfilled.

## 11. Missing and partial state map

| Observed shape | Existing truthful classification |
|---|---|
| Cycle exists, no slots | `PLANNED` can lawfully precede admission. With live ownership: incomplete. Without live ownership: interrupted/ambiguous unless exact pre-lifecycle terminal provenance establishes a safe terminal. A filled-cycle terminalizer rejects anything other than two slots. |
| Two slots, no windows | Before planning with live ownership: incomplete. Without live ownership: interrupted/ambiguous. Current Phase-A terminalizer can still terminalize this shape, so its broad cycle row is not sufficient semantic proof. |
| 1h complete, progression absent | Lane-3 derivation: `INTERRUPTED_AMBIGUOUS`, reason `STANDARD_4H_PROGRESSION_ATTEMPT_MISSING`. |
| Progression eligible, no 4h created | `ELIGIBILITY_COMPLETE` / `ELIGIBLE_NOT_CREATED`; incomplete, not success. |
| 4h graph partially absent | interrupted/ambiguous; exact missing window/job/work cannot be adapted to success. |
| Scheduler job exists, campaign-work mirror missing | correspondence incomplete; failed/ambiguous according to underlying job and ownership, always acceptance-blocking. |
| Terminal window, accounting unsynchronized | terminal token/window truth survives; accounting remains incomplete/blocked and cannot rewrite the window. |
| Runtime terminal, report missing | runtime rows remain authoritative; report completeness failed. Existing report-only summary fallback is defective. |
| Report exists, runtime rows active | inconsistent/unsafe. Current active producer checks cleanup before the normal report path, but the report row itself is not a DB-level runtime terminal constraint. |
| Exact terminal `DIRTY`/`NO_PROMOTION` | `HONEST_TERMINAL_NON_CLEAN_STATE`; safe to report, never CLEAN and never decision training authority. |

## 12. Crash / restart map

The authorized command is one-shot and has no automatic retry, restart, resume,
or successor owner. “Durably reconstructable” therefore does not mean
“authorized to resume.”

| Crash point | Current classification |
|---|---|
| A. Cycle 1 terminal truth, before Cycle-1 accounting | Runtime child truth may be durable, but the six-unit accounting owner is in memory. Interrupted/ambiguous for operator review; no authorized resume. |
| B. Cycle-1 accounting, before Cycle-2 admission | There is no separate durable cycle-accounting record; any unpersisted owner state is lost. If Cycle 1 rows are terminal they stay terminal; campaign is incomplete/interrupted. |
| C. During Cycle-2 admission | Admission transaction is atomic. Rollback leaves no partial admitted cycle, while a committed attempt/cycle remains inspectable. No automatic retry; unresolved active attempt is interrupted/ambiguous. |
| D. Cycle 2 admitted, before Scheduler claim | Exact planned jobs/work/windows are durable. They are incomplete if ownership remains live; otherwise interrupted/ambiguous requiring review. |
| E. During Cycle-2 window work | Running/locked work with live lease is active; without live owner it is interrupted/ambiguous. No recovery authority is created here. |
| F. Cycle-2 terminal persistence, before campaign accounting | Per-cycle runtime truth is durable and already terminal; campaign accounting/reporting is incomplete. Current Cycle-1 accounting defect prevents truthful normal finalization. |
| G. Campaign terminal accounting, before final report | Campaign/run runtime terminal rows are authoritative, but in-memory accounting projection can be lost and report is missing. Already runtime-terminal; reporting incomplete, no automatic regeneration authority. |
| H. Report write, before terminal summary | Immutable report row/artifact is authoritative and report-only can read it. Terminal summary is missing; no campaign rerun is needed or authorized. |
| I. Summary, before cleanup completion | This ordering is impossible on the normal success path because cleanup precedes report and summary. A failure summary can exist with cleanup unproven; such a summary is not terminal proof and the state is unsafe/incomplete. |

## 13. Idempotency and duplication audit

- Cycle uniqueness prevents duplicate ordinal-1/ordinal-2 rows in one run.
- Slot uniqueness prevents duplicate ordinals or the same token within a cycle.
- Scheduler ownership permits one campaign-work owner per Scheduler job; exact
  mirror mismatch blocks rather than silently duplicating ownership.
- Lane-3 progression is unique per campaign/run/cycle; committed handoff verifies
  exact existing successors and does not create a second handoff on replay.
- Report row/artifact persistence is idempotent only for the identical payload.
- Terminal summary writing is not create-once and can overwrite an earlier file.
- Full-run six-unit owner/action-local state is not itself a durable replayable
  accounting ledger; rerunning finalization is not generally authorized.
- The operational controller caps admitted cycles at two. Terminal accounting or
  report writing does not call admission, create windows, recreate Scheduler
  work, or trigger Cycle 3.
- No report-only path authorizes source calls, Scheduler runtime calls, database
  writes, recovery, or successor creation.

## 14. Synthetic adapter and fixture findings

`four_token_factory_adapter.build_four_token_cycle_accounting_package()` and
`build_cycle_lifecycle_ownership_context()` are referenced by focused tests but
have no production caller in the current source tree. Their success-shaped
packages are constructed from supplied fixture facts and are not the producer of
the operational campaign's terminal accounting or report.

Classification: `STALE_TEST_OR_FIXTURE_DEBT`.

The production-reachable functions in the same module—cycle reconciliation and
shared terminalization—must not be confused with those unused package builders.
Old synthetic expectations do not establish runtime correctness and should not
be repaired merely to preserve their assumptions.

## 15. Findings and exact classifications

| ID | Finding | Classification |
|---|---|---|
| L4-01 | One global status/cause is applied to every admitted cycle without consuming canonical per-cycle window/progression truth. | `PROVEN_CODE_DEFECT` |
| L4-02 | Factory-run-wide close/job rows are resolved through the initial Cycle-1 context in full-run accounting, blocking or excluding Cycle 2. | `PROVEN_CODE_DEFECT` |
| L4-03 | The canonical operational report has only initial Cycle-1 identity and cannot report the required two-cycle terminal hierarchy. | `PROVEN_CODE_DEFECT` |
| L4-04 | Terminal summaries omit `configuration_id`, while their exact production reader requires it. | `PROVEN_CODE_DEFECT` |
| L4-05 | Summary is independently derived/overwritable and lacks per-cycle semantics; lower-level cycle faults are not reconciled into report secondary evidence. | `BASELINE_ACCOUNTING_REPORTING_DEBT` |
| L4-06 | Success-shaped multi-cycle accounting package/context builders are test-only and have no current production consumer. | `STALE_TEST_OR_FIXTURE_DEBT` |
| L4-07 | No consumed historical campaign proves the post-Lane-3 combined two-cycle progression/accounting/report path; historical 4/2/2 evidence predates Lane 3 and cannot substitute. | `MISSING_EVIDENCE` |
| L4-08 | Exact terminal non-CLEAN window outcomes are valid lifecycle outcomes but remain excluded from CLEAN authority. | `HONEST_TERMINAL_NON_CLEAN_STATE` |
| L4-09 | Exact-two-cycle branches, ordinals `(1,2)`, two-cycle completion checks, Cycle-1 identity in report schema, and two-cycle controller limits cannot safely represent a future third cycle. | `FUTURE_CYCLE3_COMPATIBILITY_OBSERVATION` |

No `PROVIDER_LIMITATION` or `SOURCE_LIMITATION` was established by this static
accounting/reporting audit. No independent `DESIGN_GAP` was established: the
current schemas already produce enough lower-level cancellation/interruption
truth for a canonical composite. The current defect is the failure to
consume/report that truth, not an instruction to invent a new enum.

## 16. Baseline debt versus stale-test debt

Baseline accounting/reporting debt is production-reachable: L4-01 through L4-05
sit after real Cycle-1/Cycle-2 execution and affect terminal accounting or the
operator surfaces. L4-01 through L4-04 are proven code defects within that debt.

Stale test/fixture debt is limited to L4-06. Those builders neither admit Cycle 2
nor terminalize a real campaign. Fixture-only states have no production producer
and cannot be used as evidence for a repair.

## 17. Cycle-3 forward-compatibility observations only

The following do not break the authorized two-cycle shape by themselves:

- controller and adapter checks accept only cycle ordinals 1 and 2;
- terminal success requires exactly two admitted cycles;
- admission stops when the cycle count reaches two;
- later-cycle acquisition explicitly requires proposed ordinal 2;
- report and summary identify one initial cycle rather than a cycle collection;
- test helpers and some arrays assume two cycles/two slots.

These are `FUTURE_CYCLE3_COMPATIBILITY_OBSERVATION` items only. Cycle 3 remains
locked. No generic-N or Cycle-3 design is part of this audit.

## 18. Lane-3 / Lane-2 regression locks

No Lane-3 regression was established. The cycle-scoped production path calls
the shared Lane-3 derivation; it does not need to reconstruct immutable 1h
predecessor truth, attempt/token authority, 0/1/2 handoff, primary/secondary
fault order, or interrupted semantics. The defect is downstream failure to carry
that derivation into cycle/campaign reporting.

No Scheduler category, deadline, cadence, fairness, Source Governor,
evidence-time, or Lane-2 production rule was reopened.

## 19. Production-Path Completeness assessment

The underlying exposed states have real producers, persistence owners, and
consumers:

- cycle/slot/window/work states: campaign ownership plus factory/Scheduler;
- progression status: Lane-3 persisted aggregate plus shared derivation;
- shared campaign terminal state: supervision cleanup and terminal closure;
- acceptance: full-run accounting;
- final report: immutable report owner;
- summary: operational artifact writer and report-only fallback.

The completeness gate fails at the consumer boundary, not at production of the
underlying facts. Per-cycle cancelled/interrupted/primary-secondary report fields
do not have real current report producers. Any design must map them from the
canonical persisted rows and Lane-3 derivation; fixture injection of expected
labels is not acceptable.

Production-path verdict: sufficiently traced for design, not correct for a new
campaign. No Lane-4 implementation or proof is authorized by this audit.

## 20. Minimum design inputs if separately authorized

A separate design/specification should, at minimum, define:

1. one read-only canonical per-cycle terminal derivation that consumes exact
   campaign/run/cycle/slot/window/work/job and Lane-3 progression truth;
2. explicit token-local, cycle-shared, and campaign-shared fault precedence;
3. campaign aggregation across exactly the required admitted Cycle 1 and Cycle 2,
   including partial/incomplete and inactive-interrupted states;
4. a full-run accounting context that cannot mix factory-run-wide steps with one
   cycle predicate;
5. report and summary schemas derived from the same authoritative aggregate,
   including first cause and later secondary evidence;
6. immutable/idempotent report and summary rules plus truthful missing-report and
   missing-summary behavior;
7. crash-boundary behavior without retry, resume, restart, successor, or Cycle-3
   authority;
8. negative proof that a successful Cycle 1 cannot mask failed/incomplete Cycle 2
   and a shared campaign fault cannot be reduced to token-local failure.

These are inputs, not the Lane-4 design.

## 21. Explicit do-not-change list

Do not change or unlock in this audit closeout:

- Lane-3 immutable 1h predecessor, attempt/token authority, 0/1/2 handoff,
  first-primary/secondary preservation, or interrupted semantics;
- Lane-2 Scheduler category/deadline/fairness/cadence or evidence-time rules;
- Source Governor, Central Scheduler, tracking priorities, or source adapters;
- Cycle 3, 12h/24h, or `WINDOW_5M_MICRO_EVENT` support-only status;
- retrieval, BUY/SELL/HOLD, positions, trade events, paper audits, PnL;
- live execution, wallets, private keys, signing, real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors;
- any historical campaign, authorization, cursor, report, or evidence package.

## 22. Final verdict

The approved two-cycle execution graph and Lane-3 progression truth are real and
cycle-scoped. Campaign-end accounting and reporting are not yet correct for that
shape: they apply one shared terminal result to both cycles, resolve factory-wide
evidence through Cycle 1, omit authoritative per-cycle reporting, and produce a
summary that its own exact fallback reader cannot accept.

The audit establishes enough exact production ownership, defect evidence, and
design constraints for the next separate task:

`V2_9_8B_LANE4_MULTI_CYCLE_TERMINAL_ACCOUNTING_REPORTING_READINESS_AUDIT_PASS_READY_FOR_DESIGN`

Next permitted action: Lane 4 multi-cycle terminal accounting/reporting
**design/specification only**. Cycle 3 remains locked.

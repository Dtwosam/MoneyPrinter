# Printer V1 V2-9.8B Lane 4 Multi-Cycle Terminal Accounting / Reporting Design

Date: 2026-08-23

Lane: `V2-9.8B Lane 4 — Multi-Cycle Terminal Accounting / Reporting`

Scope: design/specification only; current authorized Cycle 1 + Cycle 2 shape

Starting HEAD: `4c0fe31f773c14f59e2008ed3f17f8f03580bb98`

Verdict:

`V2_9_8B_LANE4_MULTI_CYCLE_TERMINAL_ACCOUNTING_REPORTING_DESIGN_PASS_READY_FOR_NARROW_IMPLEMENTATION`

This document specifies the minimum repair for readiness findings L4-01 through
L4-04. It does not implement the repair, modify tests or schemas, run Printer,
regenerate a report, authorize proof/live work, or activate Cycle 3.

## 1. Source-grounded blocker classification

The Lane-4 readiness audit is the established production-path investigation.
Under the Printer Python Builder Guide, L4-01 through L4-04 are
`COMMITTED_CODE_DEFECT`: real current producers persist cycle-scoped truth, but
the committed downstream consumers collapse it through one Cycle-1 context or
an independently constructed summary.

Code change is justified only in a later narrow implementation task. Existing
schemas, Lane-3 progression, Cycle-2 admission/execution, Scheduler, Source
Governor, and evidence collection behaved as established and are not repair
targets.

## 2. Approaches considered and chosen design

### Chosen: extend the existing accounting owner

`campaign_full_run_accounting.py` already owns exact lifecycle identity,
per-cycle completeness projection, Scheduler/work correspondence, quality
consistency, full-run acceptance, and the embedded terminal evidence report.
It will own two public read-side derivations:

- `derive_cycle_terminal_accounting_result(...)`; and
- `derive_two_cycle_campaign_terminal_accounting(...)`.

The first replaces and extends
`project_cycle_lifecycle_accounting_completeness()` as the canonical per-cycle
read contract. The second composes only the authorized admitted ordinals 1 and
2. The existing projection function may remain as a narrow compatibility wrapper
that calls the new owner; it must not keep an independent interpretation.

This is the minimum change because it reuses the current durable queries and
Scheduler correspondence owner and avoids a second accounting module.

### Rejected: new terminal-accounting module

A new module would create a cleaner filename but would either duplicate the
existing completeness/correspondence queries or require a broader helper move.
That is unnecessary for the current repair.

### Rejected: repair inside the four-token adapter or report builder

`four_token_factory_adapter.py` owns terminal mutation/composition, not canonical
accounting. It also contains test-only synthetic package builders. The report
builder is a consumer, not a producer of runtime truth. Neither may become a
parallel derivation authority.

## 3. Canonical per-cycle derivation owner

Conceptual production signature:

```text
derive_cycle_terminal_accounting_result(
    connection,
    *,
    context: OperationalLifecycleOwnershipContext,
) -> exact read-only cycle terminal accounting result
```

The caller supplies identity only. The function itself resolves `cycle_ordinal`,
cycle-scoped factory-step IDs, slots, windows, progression, Scheduler jobs/work,
and ownership activity. A caller cannot inject step IDs, a finished status,
quality, fault classification, or expected outcome.

`OperationalLifecycleOwnershipContext` remains the exact per-cycle identity
carrier:

- `campaign_id`;
- `campaign_run_id`;
- `cycle_id`;
- `configuration_id`;
- `factory_run_id`;
- `expected_window_kind=WINDOW_15M`; and
- `expected_token_capacity=2`.

The derivation additionally reads and validates `cycle_ordinal` from the cycle
row. Only ordinals 1 and 2 are accepted in this lane. It orders all cycle-local
collections deterministically by ordinal and stable row identity.

### Returned axes, not a new persisted enum

The returned mapping is versioned read-side data. It is not a table or mutable
state machine. It keeps these axes separate:

| Axis | Values / meaning |
|---|---|
| `activity_state` | `ACTIVE_INCOMPLETE`, `INACTIVE_INCOMPLETE`, or `TERMINAL`; derived from durable work plus live supervision/lease ownership |
| `execution_outcome` | `TERMINAL_SUCCESS`, `CYCLE_FAILED`, `CANCELLED_STOPPED`, `INTERRUPTED_AMBIGUOUS`, or an incomplete activity state |
| `quality_outcome` | `CLEAN`, `NON_CLEAN`, `MIXED`, or `NOT_APPLICABLE`; never changes execution success into CLEAN |
| `accounting_complete` | Boolean requiring exact identity, lifecycle, progression, Scheduler/work correspondence, and zero unaccounted state |
| `requires_review` | True for inactive incomplete, ambiguous, missing, conflicting, or structurally inconsistent truth |

`TOKEN_LOCAL_FAILURE` and progression `INELIGIBLE` remain token outcomes, not
automatic cycle failure. A cycle may be execution-complete with one exact
token-local failure if Lane-3 composition is complete and no cycle-shared fault
exists. `TERMINAL_NON_CLEAN` is represented by
`execution_outcome=TERMINAL_SUCCESS` plus `quality_outcome=NON_CLEAN` or `MIXED`;
the report exposes the combined operator label without corrupting either axis.

### Exact token result

Each of exactly two token entries contains:

- slot ordinal and `token_slot_id`;
- token row/mint and pair row/address identity;
- `tracking_queue_id`, lifecycle identity, and tracking lane;
- persisted slot state;
- one summarized entry for each required `WINDOW_15M`, `WINDOW_1H`, and eligible
  `WINDOW_4H` identity/state/memory reference;
- Lane-3 progression disposition and outcome;
- Scheduler/work/factory-step terminal correspondence summary;
- token outcome: success, honest non-CLEAN, ineligible, token-local failure,
  cancelled, active/incomplete, or interrupted/ambiguous;
- exact primary fault envelope, if produced; and
- ordered secondary fault envelopes.

The 5m support window may be referenced diagnostically but never participates in
main-window completeness or continuation.

### Exact cycle completion and quality rules

Execution completion requires both exact slots, one terminal 15m and one
terminal 1h outcome for each slot, the shared Lane-3 derivation reporting a
complete composition, one terminal 4h graph for every `HANDOFF_CREATED` token,
no 4h graph for an ineligible/token-terminal-failed token, exact terminal
Scheduler/work/step correspondence, and zero unexplained active ownership.
`HANDOFF_COMMITTED` or a broad terminal cycle row alone is insufficient.

Quality is derived for every applicable main window from its campaign-window
state and exact linked memory/episode owner. `DIRTY`, `NO_PROMOTION`, partial,
or do-not-train truth remains non-CLEAN. `CLEAN_PROMOTED` and
`ALREADY_EXISTS_IDEMPOTENT` count as clean only when the linked authoritative
memory/episode contract agrees. A state/quality mismatch blocks accounting; it
is not normalized. 5m support evidence is excluded from this quality aggregate.

## 4. Producer / consumer and Production-Path Completeness map

| Derived field | Real producer and canonical rows | Production consumer | Terminal/read-side meaning | Future proof boundary |
|---|---|---|---|---|
| Cycle identity/ordinal/state | campaign cycle row | terminal adapter, campaign aggregate, report | exact admitted cycle; ordinal limited to 1/2 | foreign/missing/ordinal-3 rows block |
| Token identity/disposition | exact two campaign slot rows | cycle derivation and report | token-local state; never inferred from symbol | wrong/missing/duplicate slot blocks |
| Main-window outcome | campaign windows + linked memory row/episode | cycle derivation, quality projection | terminal lifecycle and CLEAN/non-CLEAN remain separate | missing/duplicate/wrong identity/dirty cases |
| Factory execution | cycle-scoped factory steps resolved by existing production owner | cycle derivation/full-run accounting | exact work performed for this cycle only | Cycle-2 step cannot resolve through Cycle 1 |
| Scheduler/work outcome | Scheduler job + stage-scoped campaign-work mirror | cycle derivation/full-run gate | exact terminal correspondence and active ownership | missing/mismatched/foreign mirror blocks |
| 4h progression | Migration-061 attempt/tokens via `derive_standard_4h_progression_status()` | cycle derivation and report | committed 0/1/2 handoff plus actual successor outcome | missing/partial graph is ambiguous, never success |
| Active/interrupted | factory/run/supervision lease + jobs/work/steps/windows | cycle/campaign aggregate | live unfinished versus inactive ambiguous | live and expired ownership cases |
| Token/cycle fault | progression envelope or exact failed/cancelled owned row | cycle result/report | retains originating token/cycle scope | peer token/cycle cannot overwrite |
| Campaign-shared fault | campaign/run/supervision/cancellation/global-integrity/cleanup owners | aggregate, terminalizer overlay, report | affects campaign and may stop cycles, explicitly marked shared | shared versus local negative controls |
| Per-cycle six-unit evidence | existing registered `CampaignSixUnitOwner` | full-run reconciliation | evidence only for that exact cycle | owner/action-local equality per cycle |
| Campaign evidence totals | existing `CampaignSixUnitProjection` | report totals/detail | aggregate evidence, not cycle identity or terminal status | registered-cycle set and sum equality |
| Report | canonical report builder/writer + report row/artifact | report-only, summary builder, operator | immutable durable reporting truth | identical/divergent replay cases |
| Summary | canonical aggregate plus report-write result | operator/report-only diagnostic | adapted convenience surface only | exact identity/mismatch/missing report |

Every new classification is derived from these producers. A fixture cannot
supply `execution_outcome`, `quality_outcome`, fault scope, or campaign result
directly.

## 5. Exact identity contract

### Cycle identity

Every cycle read uses all of:

```text
campaign_id
+ campaign_run_id
+ configuration_id
+ factory_run_id
+ cycle_id
+ persisted cycle_ordinal
```

Every slot/window/work/progression join adds its exact child identity. Factory
steps must be attributed through the existing cycle-scoped owner and exact
Scheduler-work/window relationship; token ID alone is never a cycle join.

### Campaign identity

The campaign aggregate uses:

```text
campaign_id
+ campaign_run_id
+ configuration_id
+ factory_run_id
+ exact admitted cycles ordered by (cycle_ordinal, cycle_id)
```

`required_cycle_ordinals` is the immutable lane constant `(1, 2)`. Iteration is
read-only. An ordinal outside `{1,2}`, more than two admitted cycles, duplicate
ordinal, wrong factory binding, or configuration mismatch is
`INTERRUPTED_AMBIGUOUS` / acceptance-blocking. It never creates or authorizes a
cycle.

### Report and summary identity

New Lane-4 reports use explicit `campaign_run_id`; they do not use a top-level
single `cycle_id`. Exact identity is:

```text
campaign_id
configuration_id
campaign_run_id
factory_run_id
execution_id
report_id
```

The summary repeats those six fields at top level and records the report hash
and path when a report is durable. Historical report versions using
`identity.run_id` remain immutable and are accepted only under their historical
versioned reader contract; they are not rewritten into the Lane-4 schema.

## 6. Token / cycle / campaign fault precedence

Every fault envelope exposes:

- `cause`;
- `origin_scope`: `TOKEN`, `CYCLE`, `CAMPAIGN`, or `REPORTING`;
- exact `cycle_id` and `token_slot_id` when applicable;
- owner/stage and stable source-row reference;
- persisted observed/terminal time when available;
- safe message/exception class only when the real producer supplied it; and
- `effect_scope`, which differs from origin only when a local fault causes the
  one-shot campaign to stop other work.

No new fault table is required. For rows that persist only cause/time, scope is
derived from their exact ownership level. Missing message/exception detail
remains absent.

### Precedence rules

1. A committed lower-level primary remains primary for that token/cycle. Lane-3
   attempt/token primary and secondary rules are reused unchanged.
2. Token-local failure, cancellation, ineligibility, or non-CLEAN quality remains
   token-local. It does not manufacture a cycle-shared cause.
3. Cycle-shared identity, Scheduler/work, or progression integrity failure may
   fail that cycle only. It cannot rewrite a peer cycle.
4. A genuine campaign supervision, cancellation, DB/global-integrity,
   forbidden-delta, accounting-owner, or required cleanup fault is
   campaign-shared and may stop every nonterminal cycle. It remains marked
   `origin_scope=CAMPAIGN`.
5. When a local cycle fault ends the bounded one-shot campaign and stops active
   peer work, the peer receives the narrow closure cause
   `CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL`, with
   `origin_scope=CYCLE`, `effect_scope=CAMPAIGN`, and a reference to the original
   cycle fault. The peer is not assigned the original local cause as its own.
   This new reason constant is necessary scope-preservation metadata, not a new
   terminal state or capability.
6. Campaign aggregate first cause uses the already persisted campaign/run first
   cause when present. Otherwise it references the first exact owner cause that
   actually ended the campaign; its origin scope remains truthful.
7. Later cycle, cleanup, accounting, report, or summary faults are secondary and
   cannot replace an existing primary. `SAFE_STOP_PREFLIGHT_FAILED` remains only
   a fallback when no exact earlier cause exists.

Primary selection never depends on re-sorting historical rows. An already
committed primary wins. Secondary presentation is deterministic by persisted
observed time, owner/stage, source reference, cycle ordinal, and slot ordinal.

## 7. Exact Cycle-1 / Cycle-2 campaign aggregate

Conceptual production signature:

```text
derive_two_cycle_campaign_terminal_accounting(
    connection,
    *,
    campaign_id,
    campaign_run_id,
    configuration_id,
    factory_run_id,
) -> read-only two-cycle campaign terminal accounting result
```

It queries the admitted cycles itself and calls the canonical per-cycle owner for
each. It never accepts fixture-built cycle results.

The same owner exposes two projections from one derivation, not two competing
authorities:

1. a runtime projection used by Phase A/Phase B, derived only from durable
   campaign rows; and
2. a finalized accounting projection used by the report, produced only after
   `finalize_full_run_ownership_and_report()` supplies its real per-cycle owner/
   action-local reconciliation and the real cleanup result.

The finalized projection may add an accounting or cleanup fault, but it cannot
replace the runtime projection's primary cause or alter a cycle result. Direct
callers and tests cannot inject a finished accounting classification; they must
create the underlying owners/rows from which the accounting function produces
it.

### Aggregation order

1. Invalid campaign/run/config/factory binding, ordinal outside `{1,2}`, or
   structurally conflicting ownership: `INTERRUPTED_AMBIGUOUS`, blocked unsafe.
2. Genuine campaign-shared failure: `CAMPAIGN_FAILED` or
   `CANCELLED_STOPPED` according to its existing persisted state/cause.
3. One or both cycle-shared failures: `CYCLE_FAILED`; each cycle history remains
   distinct and the aggregate names the failed ordinal(s).
4. Any inactive missing/partial required cycle: `INTERRUPTED_AMBIGUOUS`.
5. Any live admitted or pre-admission work: `ACTIVE_INCOMPLETE`.
6. Exactly ordinals 1 and 2 execution-complete with zero unresolved state:
   `TERMINAL_SUCCESS`. If either cycle is honestly non-CLEAN, the separate
   campaign quality is `NON_CLEAN` or `MIXED`; execution remains complete.

The aggregate contains:

- required ordinals `(1,2)`;
- exact admitted ordinal/ID pairs;
- one complete per-cycle result in ordinal order;
- aggregate execution and quality outcomes;
- failed/active/interrupted cycle ordinals;
- exact campaign first-cause envelope and secondary faults;
- zero-active-work/cleanup/reconciliation facts when available;
- `accounting_complete`; and
- `campaign_pass_eligible`, which is only an input to the existing acceptance
  gate, never the final verdict by itself.

A one-cycle exact no-admission or pre-lifecycle zero-attempt state remains an
honest stopped/blocked terminal, never two-cycle success. No persisted
`PARTIALLY_COMPLETE` state is added.

Reporting completeness is a separate read-side axis:

- `REPORT_PENDING` when runtime/accounting is terminal but no exact report row
  exists;
- `REPORT_DURABLE` when row and artifact match; and
- `REPORT_MISMATCHED` when row/artifact/identity disagree.

This axis is read after report lookup and is not embedded as self-referential
truth inside the report being written.

## 8. Shared-terminalization correction

The global `cycle_run_status` loop in `run_one_command_15m_factory` is removed.
No caller may pass one arbitrary cause/status to every cycle.

For each admitted ordinal in deterministic order:

1. derive that cycle's exact pre-terminal composite from durable rows;
2. resolve any genuine campaign-shared or peer-stop effect separately;
3. call `reconcile_four_token_cycle_terminal` with exact identity and the
   canonical derivation owner, not caller-supplied finished classification;
4. cancel only that cycle's still-active Scheduler work/windows/steps when a
   truthful stop effect requires it;
5. map the derived outcome onto existing broad cycle states:
   - complete, including honest non-CLEAN/token-local outcomes ->
     `TERMINAL_COMPLETED` with existing completion cause;
   - cycle-shared failure -> `TERMINAL_FAILED` with exact cycle cause;
   - cancellation/peer/shared stop -> existing stopped/blocked mapping with the
     exact scoped cause;
   - unexplained inactive/partial truth -> `TERMINAL_BLOCKED` / review, never
     success;
6. re-read the cycle through the same derivation and require zero active owned
   work plus agreement with the written broad state.

Already-terminal cycle rows remain immutable. A differing replay fails closed.
An `ACTIVE_INCOMPLETE` cycle cannot be terminalized without exact campaign-shared
or peer-stop authority. Missing provenance yields ambiguity and blocks Phase B.

`finalize_four_token_shared_terminal` then consumes the canonical campaign
aggregate. Two-cycle success requires exact ordinals 1 and 2 and both complete.
The existing honest one-cycle no-admission shapes remain stopped/blocked special
cases. Phase B still calls the one supervision cleanup/shared campaign owner
exactly once and creates no successor.

## 9. Full-run accounting correction

`finalize_full_run_ownership_and_report()` changes from one cycle context to an
exact ordered set of per-cycle contexts derived from the campaign aggregate.

Conceptually, its single `context` parameter is replaced by an exact campaign
identity plus `cycle_contexts` constructed internally from the admitted cycle
rows. Callers cannot choose an arbitrary subset or order. The registered cycle
owner set and the internally constructed context set must agree exactly before
any acceptance calculation.

For each admitted cycle it must:

1. derive its factory-step IDs through the existing cycle-scoped production
   owner;
2. select close steps/jobs/work/windows only from that set and exact
   campaign/run/cycle/slot/window relationships;
3. run the canonical cycle terminal accounting derivation;
4. reconcile the corresponding registered `CampaignSixUnitOwner` against the
   execution-time action-local evidence slice for that cycle; and
5. preserve every missing, duplicate, foreign, active, failed, or mismatched row
   as a fail-closed cycle reason.

No query may select factory-run-wide rows and then resolve them with one
`context.cycle_id`. Token ID is not sufficient attribution even though current
admission also enforces cross-cycle disjointness.

The final report input includes `cycle_accounting_results` in ordinal order and
one campaign aggregate. The acceptance gate requires:

- exact required cycles `(1,2)` for success;
- both cycle accounting results complete;
- exact Scheduler correspondence per cycle;
- Lane-3 progression consumed from its owner;
- aggregate owner/action-local evidence equality;
- runtime terminal completion, zero active/locked work, released lease, exact
  authorization/invocation, no forbidden delta, and no retry/restart/resume/
  successor.

An honest non-CLEAN/token-local outcome does not become execution failure, but it
cannot be presented as CLEAN. A missing second cycle, progression aggregate, 4h
graph, campaign-work mirror, or report input always prevents campaign PASS.

## 10. Six-unit accounting decision

`CampaignSixUnitProjection` remains a read-only aggregate evidence/detail object.
It is not replaced, and no new ledger is added. Its `registered_cycle_ids` must
equal the admitted cycle IDs used by the canonical aggregate.

It no longer supplies an authoritative `owner_id`/`cycle_id` by borrowing the
primary Cycle-1 owner for campaign acceptance. Instead:

- each registered cycle owner is reconciled under its own exact cycle context;
- its sealed stage set includes that cycle's terminal reconciliation evidence;
- action-local evidence is partitioned by exact cycle-bearing stage IDs/owned
  job/window identities;
- the execution-time `CampaignActionLocalLedger` is campaign/run scoped rather
  than identified as Cycle 1; and
- the campaign projection only validates concatenation, multiplicity, total
  reconstruction, and the exact registered-cycle set.

Terminal reconciliation evidence is sealed once for each admitted cycle owner,
not once into the initial Cycle-1 owner. This is accounting/reporting work only;
it does not change source measurement, budgets, Scheduler behavior, or lifecycle
evidence acquisition.

## 11. Canonical campaign report contract

`build_campaign_terminal_report()` and `write_campaign_terminal_report()` remain
the sole active report builder/persistence path. The report schema advances to a
Lane-4 version so historical payloads remain immutable.

### New report shape

```text
identity
  campaign_id
  configuration_id
  campaign_run_id
  factory_run_id
  execution_id
  report_id

terminal_accounting
  required_cycle_ordinals: [1, 2]
  execution_outcome
  quality_outcome
  accounting_complete
  first_cause
  secondary_faults
  cleanup/reconciliation summary

cycles: [ordered Cycle 1 result, ordered Cycle 2 result]

campaign_acceptance
six_unit_totals/evidence
clean_memory_outcome
permanent locks
```

Each cycle contains the fields specified in section 3. Lower-level rows are
summarized with exact IDs/states; raw full step/job/evidence payloads are not
duplicated when the canonical row can be referenced. The existing full-run
evidence becomes cycle-grouped detail under the same aggregate rather than a
Cycle-1-scoped competing report.

The report's `terminal.first_terminal_cause` compatibility surface, if retained,
must be a projection of `terminal_accounting.first_cause`, not a second input.
The report builder may not accept a separate global `cycle_id`, status, or cause
that can disagree with the aggregate.

Persistence remains unchanged in authority:

- one exact report identity;
- canonical deterministic JSON;
- one immutable DB row and matching artifact;
- identical replay idempotent;
- differing payload rejected;
- no source, Scheduler, lifecycle, or database repair work.

## 12. Terminal-summary contract

The summary becomes a compact projection of the already-built canonical
aggregate plus the report-writer result. It never queries lifecycle rows to
recompute cycle truth.

### Required summary fields

```text
status
campaign_id
configuration_id
campaign_run_id
factory_run_id
execution_id
report_id
report_status / report_hash / terminal_report_path
campaign execution_outcome / quality_outcome / accounting_complete
campaign first_cause / secondary_faults
cycles: [{cycle_id, cycle_ordinal, execution_outcome,
          quality_outcome, requires_review, primary fault reference}]
cleanup_complete / lease_released / active_work
restart_created=false / successor_created=false
permanent lock summary
```

When report persistence failed or cleanup is unproven, the same canonical
aggregate may produce a failure summary with `report_status=REPORT_MISSING` and
no success claim. It cannot substitute for the missing report.

For an existing pre-lifecycle failure branch with no factory/cycle aggregate,
the summary uses the real activation/pre-admission terminal projection, emits an
empty cycle list, sets `accounting_complete=false`, and cannot claim multi-cycle
success. This is a versioned pre-lifecycle diagnostic shape, not a second
terminal-accounting authority.

### Summary writer

`unified_terminal_closure.py` owns a single
`write_campaign_terminal_summary()` helper alongside the report artifact owner.
All current success/failure summary branches call it; direct `Path.write_text()`
branches are removed.

The helper uses the report writer's canonical serialization and sibling
temporary-file, file-fsync, replace, read-back pattern. Before replacement it
checks an existing destination:

- identical canonical bytes -> idempotent existing result;
- different bytes -> `TerminalClosureError`, never overwrite; and
- absent -> write, fsync, replace, and read back under the single authorized
  summary writer.

Focused tests must prove the supported host behavior and differing-file guard.
No second concurrent summary writer is authorized. Missing summary after a
durable report leaves runtime/report truth valid and is reported as adapted
artifact incompleteness only.

## 13. Report-only contract

`report_only()` remains SQLite read-only (`mode=ro`), zero-source, zero-Scheduler,
zero-runtime, and zero-write.

Order:

1. resolve exact campaign/run/configuration/execution identity;
2. prefer exactly one immutable terminal report row and matching artifact;
3. validate the report's versioned identity and return its already-persisted
   per-cycle aggregate without recomputing lifecycle truth;
4. if no report exists, load the summary only with exact campaign,
   campaign-run, configuration, execution, factory-run and report identity;
5. a valid summary without a report returns `REPLAY_BLOCKED` /
   `EXACT_TERMINAL_REPORT_MISSING`; it supplies diagnostics only;
6. a missing/malformed/mismatched summary also fails closed; and
7. report/summary identity, report hash, aggregate status, or cycle-list mismatch
   returns an explicit replay block.

The reader requires `configuration_id` because every new producer writes it.
Historical summary files missing that identity remain honestly mismatched. No
report or summary regeneration, historical configuration inference, database
write, or recovery is added.

## 14. First-cause and secondary-fault contract

- Existing row/triggers and Lane-3 primary immutability remain authoritative.
- Per-token results expose token primary and secondary faults without elevating
  them automatically.
- Per-cycle primary is the committed cycle-shared fault, if any. Token primaries
  remain nested when the cycle completes composition.
- Campaign first cause is the immutable persisted campaign/run cause plus its
  truthful origin scope/reference. If it originated in a cycle, it is not
  relabeled campaign-shared.
- A peer-stop effect references, but does not copy as local, the originating
  cycle cause.
- Cleanup/accounting/report/summary faults append as secondary after an earlier
  runtime primary.
- A later Cycle-2 fault cannot alter Cycle-1 terminal row or primary. A Cycle-1
  fault cannot be written as Cycle-2's local cause.
- Missing historical cause/message/scope detail is not invented or backfilled.

## 15. Crash / interruption semantics

| Boundary | Durable authority and required interpretation |
|---|---|
| A. Cycle 1 terminal before accounting consumption | cycle/slot/window/work/progression rows remain runtime authority; no process restart/resume is authorized, and any later inspection is read-only under separate authority |
| B. Before Cycle-2 admission | Cycle 1 remains intact; live pre-admission means active/incomplete, inactive missing Cycle 2 means stopped/ambiguous according to exact attempt provenance; never success |
| C. During Cycle-2 admission | atomic admission rollback/commit remains Lane-2/3 owner truth; no Lane-4 retry |
| D. Cycle 2 admitted before claim | planned exact ownership is active only with live owner; otherwise interrupted/ambiguous |
| E. During Cycle-2 work | job/work/step/lease decide active versus interrupted; no recovery authority |
| F. Both cycle truths durable before campaign accounting | canonical derivation is reconstructable read-only; accounting/report still pending; no lifecycle rerun |
| G. Campaign terminal rows durable before report | runtime terminal truth remains authoritative; report state is `REPORT_PENDING`/missing and report-only blocks; no regeneration authority |
| H. Report durable before summary | report row/artifact is authoritative; missing summary is non-authoritative adapted-artifact debt only |
| I. Failure summary with cleanup incomplete | summary must say cleanup unproven/report missing and cannot claim terminal success or override active runtime rows |

No boundary authorizes automatic retry, resume, restart, recovery, campaign
successor, additional cycle, or report regeneration.

## 16. Idempotency and duplication rules

- Per-cycle derivation is read-only and deterministic for one committed DB state.
- Cycle terminal replay accepts only an identical already-terminal state/cause;
  divergence fails closed.
- Lane-3 committed handoff remains verify-only and is never recreated.
- Full-run accounting partitions existing exact rows; it does not create windows,
  jobs, work, progression, or cycles.
- Per-cycle terminal stage evidence is sealed once on its registered owner;
  duplicate stage identity blocks.
- Campaign evidence projection contains each admitted cycle owner once.
- Report row/artifact and summary artifact accept identical reproduction only.
- Report-only writes nothing.
- No accounting/report call can invoke admission, and ordinal 3 is rejected.

## 17. Schema / migration assessment

**Migration required: no.**

Existing cycle, slot, window, Scheduler/work, factory-step, Migration-061
progression, supervision, campaign/run, report, and configuration rows already
persist the required lower-level truth. The missing behavior is canonical
derivation, exact per-cycle consumption, payload structure, and immutable summary
writing.

The read-side outcome/fault-scope structures are derived mappings carried into
the existing immutable report payload. `CampaignSixUnitProjection` and action-
local evidence are in-process accounting evidence, not missing durable runtime
truth. No new terminal enum, accounting table, report table, summary table, or
historical backfill is justified.

## 18. Expected narrow implementation files

### Production

| File | Expected change |
|---|---|
| `src/printer_v1/operator_cli/campaign_full_run_accounting.py` | canonical cycle and two-cycle derivations; exact per-cycle partitioning/reconciliation; cycle-aware acceptance/report input |
| `src/printer_v1/operator_cli/four_token_factory_adapter.py` | consume canonical per-cycle outcomes; remove arbitrary shared status/cause authority; verify shared aggregate |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | remove global `cycle_run_status` fan-out; invoke exact per-cycle terminalization and aggregate |
| `src/printer_v1/sources/campaign_six_unit_accounting.py` | campaign/run-scoped action-local identity and per-cycle evidence slicing; projection remains subordinate aggregate evidence |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | per-cycle terminal evidence sealing; cycle-aware full-run call; report/summary inputs; no direct summary writes |
| `src/printer_v1/operator_cli/unified_terminal_closure.py` | Lane-4 report payload, deterministic immutable summary builder/writer, version-aware report-only validation |

No change is expected in Cycle-2 admission, Scheduler, Source Governor,
`standard_4h_progression.py`, Migration 061, cadence/evidence acquisition,
`final_campaign_report.py`, provider adapters, or database schema.

### Focused tests

Expected test scope:

- new `tests/test_v2_9_8b_lane4_multi_cycle_terminal_accounting.py` for canonical
  derivation/aggregation from underlying rows;
- `tests/test_v2_9_8b_four_token_factory_terminal_integration.py` and
  `tests/test_v2_9_8b_four_token_gate_g_two_phase_terminal.py` for production
  Phase A/Phase B wiring;
- `tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py` and
  `tests/test_v2_9_8b_full_run_wiring_integration.py` for exact Cycle-2
  accounting;
- `tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py` and
  `tests/test_v2_9_8b_window_15m_checkpoint7_terminal_closure.py` for report,
  summary, and report-only contracts; and
- the existing Lane-3 module as a direct regression lock, without modifying its
  production semantics.

Synthetic package-builder tests are not design authority.

## 19. Minimum future focused implementation/proof plan

All tests construct underlying campaign rows, windows, jobs/work, steps,
progression, supervision, faults, and artifacts. They do not inject a completed
cycle/campaign classification.

1. Cycle 1 succeeds; Cycle 2 succeeds -> exact two-cycle terminal success.
2. Cycle 1 succeeds; Cycle 2 has an exact cycle-local failure -> Cycle 1 remains
   successful; campaign identifies failed Cycle 2.
3. Cycle 1 fails locally; Cycle 2 retains independent success/stop truth and does
   not receive Cycle 1's local cause.
4. One progression token `TERMINAL_FAILED` with a complete peer remains
   token-local and does not manufacture cycle-shared failure.
5. A real supervision/lease/global-integrity fault is marked campaign-shared and
   affects nonterminal cycles without changing origin scope.
6. Exact `DIRTY`/`NO_PROMOTION` terminal memory remains non-CLEAN while lifecycle
   execution completes.
7. Cycle-2 close steps/jobs resolve only through Cycle-2 slot/window/work identity;
   a Cycle-1 predicate cannot accept them.
8. Missing Cycle-2 progression or partial 4h graph yields interrupted/ambiguous
   and prevents campaign PASS.
9. Existing campaign first cause survives later Cycle-2/report/summary faults;
   later faults are secondary.
10. Canonical report contains ordinals 1 and 2 with exact identities/outcomes.
11. Summary contains `configuration_id` and both cycle statuses and is derived
    from the same aggregate/report.
12. Identical report/summary artifacts are idempotent; differing summary and
    report/summary hash or identity mismatch fail closed without overwrite.
13. Report durable with summary absent remains truthful and report-only readable.
14. Direct use of stale synthetic package/context builders cannot establish the
    production proof; production wiring proof reaches the canonical owner.
15. Explicit zero-change assertions cover Cycle 3, 12h/24h, retrieval, decisions,
    financial tables, Source Governor calls, Scheduler authority, retry/restart/
    resume/successor, and report-only writes.

Minimum commands later: the new Lane-4 test module, directly affected terminal/
full-run/report modules, Lane-3 regression module, compile/import checks for
changed production files, and diff/unlock scans. No broad suite is specified.

## 20. Stale fixture debt treatment

`build_four_token_cycle_accounting_package()` and
`build_cycle_lifecycle_ownership_context()` remain test-only helpers and are not
called by the design. They are not repaired to manufacture Lane-4 success.

If a later implementation test still needs them, its assertions may be changed
only after the production derivation and wiring test proves the new contract.
They cannot inject `execution_outcome`, fault scope, aggregate status, or report
cycles as finished facts.

No consumed historical 4/2/2 campaign is reinterpreted. Later proof uses an
isolated disposable database with production owners. A live campaign would
require a separate post-implementation/closeout authorization and is not part of
this design.

## 21. Cycle-3 future observations only

The collection-shaped report and read-only iteration avoid a last-cycle-wins
report, but this does not authorize a third cycle. The current aggregate:

- fixes required ordinals to `(1,2)`;
- rejects ordinal 3 or more than two admitted cycles;
- does not change admission or controller capacity;
- creates no generic successor behavior; and
- contains no Cycle-3 test as a current success case.

A future separately approved Cycle-3 lane would need to revisit cardinality,
policy, budgets, lifecycle authority, report version, and proof. None is designed
here.

## 22. Do-not-change and permanent locks

Do not change during Lane-4 implementation:

- Cycle-2 acquisition, admission, slot identity, or lifecycle execution;
- Lane-3 Migration-061 attempt/token/predecessor/handoff/fault semantics;
- Lane-2 Scheduler authority/category/deadline/fairness/cadence or evidence time;
- Source Governor, provider contracts, budgets, or source acquisition;
- token tracking priority or 5m support-only law;
- Cycle 3 or 12h/24h;
- retrieval, BUY/SELL/HOLD, positions, trade events, paper audits, PnL;
- live wallet/private key/signing/funds/execution;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, vectors;
- historical authorizations, campaigns, reports, cursors, or evidence.

## 23. Functionality risks / setbacks / efficiency blockers

- The current terminal flow spans large legacy modules. The implementation must
  keep the new derivation in the existing accounting owner and avoid opportunistic
  refactoring.
- Action-local evidence is in memory and stage-scoped; exact per-cycle slicing
  must prove complete stage identity rather than infer from list position.
- A crash before report persistence leaves no report authority by design. The
  repair improves truthful classification, not recovery authorization.
- Historical reports remain under older schemas and may lack Lane-4 cycle
  detail. They stay immutable and cannot prove the new path.
- Non-CLEAN, token-local failure, cycle failure, campaign failure, and reporting
  failure are deliberately separate axes; collapsing them for a shorter payload
  would reintroduce the defect.

## 24. Implementation-readiness verdict

Existing production rows can represent all required truth; no migration or new
ledger is necessary. The design assigns one canonical read owner, preserves
fault scope and first cause, fixes exact per-cycle accounting, keeps the existing
immutable report owner, makes summary a deterministic subordinate artifact, and
keeps Cycle 3 and every financial capability locked.

`V2_9_8B_LANE4_MULTI_CYCLE_TERMINAL_ACCOUNTING_REPORTING_DESIGN_PASS_READY_FOR_NARROW_IMPLEMENTATION`

Next permitted action after operator review: a separate narrow Lane-4
implementation task only. No campaign or proof is authorized by this design.

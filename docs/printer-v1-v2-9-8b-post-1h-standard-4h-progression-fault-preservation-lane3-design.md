# Printer V1 V2-9.8B Lane 3 Design

## Post-1H Standard-4H Progression + Fault Preservation

Date: 2026-08-23
Starting HEAD: `eefc1df8ffee3b91f85571511f97c0d6c9b9811c`

## Verdict

`V2_9_8B_LANE3_POST_1H_STANDARD_4H_PROGRESSION_FAULT_PRESERVATION_DESIGN_PASS_READY_FOR_NARROW_IMPLEMENTATION`

The minimum complete repair is ready for a separate narrow implementation.
It adds a durable progression aggregate, consumes existing production
authorities, and extends the existing atomic Standard-4H handoff. It does not
change Standard-4H evidence or execution policy and does not authorize a run.

This design uses the accepted Lane-3 readiness audit as the production-path
map. It does not reconstruct the missing historical consumed-run exception.

## 1. Chosen progression owner

The production owner is a new `standard_4h_progression` coordinator invoked by
the existing factory coordinator after exact first-hour lifecycle transitions.
Its durable aggregate has:

- one progression-attempt row for an exact campaign run and cycle; and
- exactly two progression-token rows, one for each exact campaign token slot.

The attempt is created in the same transaction that first persists the
standard first-hour handoff set. It therefore exists before either first-hour
predecessor can terminalize. Each committed first-hour terminal transition,
including failure or cancellation, invokes the progression coordinator in a
new post-commit scope. The coordinator never owns source work and is not a
worker loop or Scheduler job.

Three alternatives were rejected:

1. Extending successful close-step `result_json` would keep progression under
   the predecessor it must not rewrite and cannot represent an interrupted
   attempt safely.
2. Reusing campaign windows, token-slot state, or stage-scoped Scheduler work
   would respectively fabricate a 4h window before eligibility, overload one
   lifecycle scalar, or create fake Scheduler work with no Scheduler job.
3. A single JSON campaign object would weaken relational identity, state
   transitions, and crash inspection. Existing immutable `CONTINUATION_4A`
   objects remain 15m->1h decisions and are not overloaded.

The selected two-table aggregate is the smallest persistence extension that
can truthfully own shared attempt state and two independent token dispositions.

## 2. Producer and consumer map

| Runtime concept | Real producer | Persistence owner | Production consumers | Terminal behavior and focused proof boundary |
| --- | --- | --- | --- | --- |
| Standard-4H progression attempt | the existing standard first-hour handoff transaction, only when `standard_four_hour_campaign` is enabled | `printer_memory_factory_standard_4h_progression_attempts` | progression coordinator, handoff planner, terminal validator, full-run accounting, terminal closure, final report | one row per campaign-run/cycle; prove no first-hour plan can commit without it |
| Token progression disposition | progression coordinator reading exact committed predecessor and authority facts | `printer_memory_factory_standard_4h_progression_tokens` | subset planner, budget reader, accounting/reporting | one row per exact slot; prove the 0/1/2 subset and peer isolation from underlying predecessor outcomes |
| Authority evidence consumed | progression coordinator using existing health, budget, cadence, window and supervision owners | immutable `authority_evidence_json` on the attempt and `eligibility_evidence_json` on each token row | accounting, report, focused authority-origin proof | stores values and source identities actually read; no caller-supplied health booleans |
| Primary and secondary progression faults | first catching progression boundary; later terminal cleanup/report boundaries append only secondary facts | `first_terminal_cause` plus validated `fault_details_json` on the affected attempt or token row | terminal closure, run/cycle/campaign first-cause sync, accounting, final report and terminal summary | first compare-and-set wins; prove a later cleanup/report exception cannot replace it |
| 4h handoff completion | existing `plan_standard_campaign_4h_handoff` transaction, extended to compare-and-update the progression aggregate | the two-row progression manifest plus existing window, slot, step, Scheduler job and campaign work tables | Scheduler loop, validators, accounting/reporting | all-or-none 0/1/2 handoff; prove rollback and duplicate rejection |
| Canonical reported progression state | `derive_standard_4h_progression_status` reading the attempt/token aggregate and existing 4h lifecycle graph | no new row; the persisted aggregate and existing lifecycle rows are its sole inputs | terminal validator, full-run accounting, final report and terminal summary | deterministic read-side result; prove all consumers agree for absence, pending, terminal and ambiguous cases |

The complete two-row disposition set is the new Standard-4H eligibility
manifest. New runs must stop writing eligibility back into a successful close
step's `result_json`. Existing close-result manifests are historical read-only
compatibility evidence only. When one is present, a consumer may compare it to
the progression rows; disagreement is integrity failure, never an alternate
eligibility authority.

## 3. Exact identity contract

The attempt row binds immutable:

- `progression_attempt_id`;
- campaign and configuration identity;
- campaign-run identity;
- authoritative factory-run identity;
- cycle identity; and
- policy version fixed to Standard-4H progression V1.

There is one attempt per `(campaign_id, campaign_run_id, cycle_id)`. Its stable
identity is derived from that tuple; it is not a random replay opportunity.

Each of its exactly two token rows binds immutable:

- slot ordinal and `token_slot_id`;
- token identity and token row ID;
- mint identity;
- pair identity and pair row ID;
- root lifecycle identity;
- exact `tracking_queue_id` and resolved `tracking_lane`;
- exact predecessor campaign `WINDOW_1H` identity when one was planned; and
- the predecessor physical memory-window ID once a successful terminal close
  binds it.

The predecessor physical memory ID is the only one-time nullable identity. It
may move from null to one exact value after successful close binding and can
never change afterward. A slot for which no first-hour predecessor was planned
is immediately ineligible; null does not mean “wait forever.”

Foreign keys and read-back checks bind the attempt to the campaign run/cycle,
the factory run through `campaign_runs.authoritative_run_id`, and token rows to
the exact campaign slot and tracking queue. The existing
`resolve_campaign_slot_cadence_authority` chain resolves the lane from
`token_slot.tracking_queue_id -> printer_tracking_queue`; close-result or
supporting-context lanes are corroboration only. Queue token/pair mismatch,
missing queue identity, or invalid lane fails closed.
The queue lane is captured when the attempt is created and re-resolved before
eligibility; disagreement is integrity failure rather than silent lane drift.

Cycle 1 and Cycle 2 use their exact existing cycle IDs and cycle-scoped step
keys. No ordinal inference may create Cycle 3, and no attempt can span cycles.

## 4. Progression state and disposition contract

Attempt states are limited to:

- `WAITING_FOR_PREDECESSORS`: not yet evaluated, or legitimately waiting on an
  exact planned peer whose 1h work is still active;
- `EVALUATING`: the durable marker written before authority and eligibility
  evaluation;
- `ELIGIBILITY_COMPLETE`: both token dispositions are durable; any eligible
  tokens have not yet completed handoff;
- `HANDOFF_COMMITTED`: the exact 0/1/2 handoff transaction committed, including
  the explicit zero-token no-op;
- `TERMINAL_FAILED`: shared progression or handoff failure;
- `TERMINAL_CANCELLED`: a shared durable operator/external stop; and
- `INTERRUPTED_REVIEW`: a caught interruption with uncertain progression
  outcome requiring explicit review.

Token dispositions are limited to:

- `WAITING_FOR_PREDECESSOR`;
- `ELIGIBLE_PENDING_HANDOFF`;
- `INELIGIBLE` with exact reason codes and predecessor cause/reference;
- `HANDOFF_CREATED` with exact successor campaign-window identity; and
- `TERMINAL_FAILED` with an exact token-local progression fault.

`EVALUATING` left active by abrupt process death is itself a durable ambiguous
marker. A read-only consumer reports it as interrupted/ambiguous once the
owning campaign is no longer live; it never reports success. Only existing
operator-authorized recovery/terminal closure may convert it to
`INTERRUPTED_REVIEW`. There is no automatic recovery transition.

Failed or cancelled predecessor work is an `INELIGIBLE` token disposition with
`PREDECESSOR_1H_FAILED` or `PREDECESSOR_1H_CANCELLED` and a reference to its
durable first cause. Honest hard-gate failures are also `INELIGIBLE`, retaining
the evaluator's categorical reasons. They are not progression technical
failures. An identity/integrity exception scoped to one token is
`TERMINAL_FAILED`; a genuine campaign/lease/DB/global-budget fault terminalizes
the attempt.

Transitions use compare-and-update checks plus schema triggers. Identities,
completed eligibility evidence, primary cause, and terminal states are
immutable. No transition returns to waiting or creates a new attempt.

## 5. Real authority inputs

The progression coordinator accepts exact identity and the existing immutable
`OperationalDatabaseTargetBinding` already carried through the live owner and
factory stack. It must not accept health, eligibility, cancellation, lane, or
budget booleans from callers.

| Required input | Existing producer and exact value consumed |
| --- | --- |
| Campaign/run/cycle | `printer_memory_factory_campaigns.campaign_state`, `campaign_runs.run_state` and `authoritative_run_id`, `campaign_cycles.cycle_state`, `printer_memory_factory_runs.run_status`, and immutable factory `config_json.standard_four_hour_campaign`; the campaign, run, cycle and factory run must be the exact bound graph, Standard-4H must be required, and the graph must be live for new child work |
| Supervision/lease | `campaign_supervision.inspect_campaign_supervision` over the unique campaign-run supervision row and its exact lease file; consume `supervision_state`, `lease_expired`, `new_child_work_allowed`, lease expiry, and identity agreement |
| DB/schema/integrity | the existing durable `OperationalDatabaseTargetBinding`, `load_durable_operational_database_target_expectation`, `validate_operational_database_target_binding`, `validate_runtime_schema_connection`, exact `PRAGMA database_list` path, foreign-key-enabled SQLite transaction, and actual SQLite errors; do not create a second health ledger or synthesize a current `integrity_check` result |
| Shared lifecycle/Scheduler integrity | `authoritative_admission_health.project_scheduler_health`, `campaign_active_work_report`, exact campaign-scoped job IDs, stage-scoped ownership rows, job status/lock consistency, and orphan/duplicate checks; consume the exact first-cycle/cycle-owned projection, not a constant `shared_integrity_healthy=True` |
| Cancellation/external stop | supervision `cancellation_requested_at`/`cancellation_reason`, campaign/run `STOP_REQUESTED`, and the existing cooperative probe that combines heartbeat `poll_failure()` with the persisted cancellation reason; check before `EVALUATING` and again immediately before handoff |
| Campaign budget | `standard_campaign_lifecycle_budget` for the exact lanes and durable eligible mask, the approved scaled capacity contract when the existing 4/2/2 mode requires it, `_run_request_count`, campaign-scoped Scheduler/job counts, and `require_projected_capacity`; actual usage plus the exact planned suffix must fit |
| Token budget | `cumulative_lifecycle_budget`/`runtime_budget` for the exact queue-owned lane, `_token_request_count` for the exact cycle-scoped token step-key prefix, and the exact planned 4h suffix; an exhausted token is locally ineligible unless the existing policy proves the breach is global |
| Tracking identity and lane | the campaign slot's exact non-null `tracking_queue_id`, the referenced queue token/pair, and `resolve_campaign_slot_cadence_authority`; current queue status is recorded, while historical lane remains authoritative for an already-bound window |
| 1h predecessor | exact campaign window and slot state, exact close step/job/work terminal state, bound physical `printer_memory_windows` row, clean episode/promotion, safety, continuity, freshness, evidence and provenance owners already used by `operational_standard_4h` and `campaign_ownership` |

The existing `authoritative_admission_health.project_operational_health` logic
is the reusable read-side composition for campaign, supervision, lease, DB,
cancellation and shared-terminal facts. Implementation may factor its common
portion, but must not copy it into a divergent Standard-4H health authority.
Provider capacity is not a progression eligibility input; actual 4h source
scarcity remains governed execution truth after handoff.

## 6. Immutable predecessor rule

Once the first-hour transaction has committed:

- a successful close step, Scheduler job, stage-scoped campaign work, campaign
  window and physical memory binding cannot be changed by progression code;
- the progression callback runs outside the claimed step's execution/exception
  handler and receives no authority to call `_update_step`, `fail_job`, or 1h
  terminal reconciliation;
- a progression exception is caught by the progression coordinator and stored
  on the attempt/token progression row; and
- cleanup may move the campaign run/cycle and token lifecycle forward to a
  legal terminal state, but it may not rewrite the predecessor window or its
  already-terminal step/job/work.

The same separation applies after a committed failed or cancelled predecessor:
progression references that cause; it does not replace it.

## 7. First-cause and secondary-fault contract

`fault_details_json` has one canonical safe envelope:

```text
primary: cause, scope, stage, exception_class, safe_message, source_reference,
         observed_at
secondary[]: cause, stage, exception_class, safe_message, observed_at
```

The first progression boundary that can safely persist a failure performs an
atomic null-to-value compare-and-set of `first_terminal_cause` and `primary`.
Schema triggers prohibit changing either after assignment. Later cleanup,
reconciliation, accounting or report failures append to `secondary[]` by
compare-and-update and cannot edit the primary. Safe messages follow existing
redaction rules; arbitrary provider payloads and secrets are never stored.

Propagation follows these rules:

1. A token-local progression fault is primary on that token disposition.
2. A shared progression/handoff/cancellation/interruption cause is primary on
   the attempt.
3. If that cause terminalizes run/cycle/campaign/supervision state, existing
   first-cause fields receive the same exact cause only when still null.
4. A progression failure creates no fake Scheduler job, campaign work row, or
   4h window. “Through Scheduler/work/window where applicable” begins only
   after handoff; their existing exact first-cause contract remains active.
5. The successful predecessor surfaces remain successful. Slot terminalization
   by shared cleanup carries the progression primary forward; it does not write
   backward to the 1h window.
6. Canonical report and terminal summary select the progression primary before
   a generic `SAFE_STOP_PREFLIGHT_FAILED`; a generic later stop is secondary.

If SQLite itself cannot accept the primary write, the existing supervision
heartbeat/lease-file emergency evidence is the fallback evidence location. A
later authorized terminal reconciliation imports that exact safe cause; it
does not invent the missing historical consumed-run exception.

## 8. Atomic 0/1/2 token isolation contract

Each predecessor terminalizes independently. The progression producer maps an
actual failed/cancelled/ineligible predecessor to its own token row and waits
only while the peer has exact active 1h work. Missing or contradictory peer
identity is not waiting; it is an integrity fault.

When both token rows can be evaluated, one transaction writes the complete
two-row disposition set and moves the attempt from `EVALUATING` to
`ELIGIBILITY_COMPLETE`. The eligible subset may contain zero, one, or two
slots. Token-local failure cannot change the peer's disposition or campaign
truth. Only a shared campaign/run, supervision/lease, DB/integrity,
cancellation, or global-budget cause can stop the entire attempt.

An eligible token can therefore progress even when its peer's 1h predecessor
failed or was cancelled. An ineligible token receives no 4h window, step, job,
work row, or slot advancement.

## 9. Atomic handoff transaction

The existing clean transaction in `plan_standard_campaign_4h_handoff` remains
the handoff owner. It is extended, not replaced. From an exact
`ELIGIBILITY_COMPLETE` attempt, one transaction must:

1. re-read and compare the immutable two token dispositions and real authority
   preconditions;
2. derive the exact eligible subset and approved campaign/token budgets;
3. verify the complete frozen two-row progression manifest without modifying
   either predecessor close step;
4. create one campaign `WINDOW_4H` for each eligible token;
5. create all eligible `LONG_CONTINUATION_*` run steps and Scheduler jobs;
6. project every job to exact V2 stage-scoped `WINDOW_4H` campaign work;
7. advance eligible slots only to `WINDOW_4H_CONTINUING`;
8. move eligible token dispositions to `HANDOFF_CREATED` and bind successor
   window identities; and
9. move the attempt to `HANDOFF_COMMITTED` after full read-back verification.

For zero eligible tokens, steps 3 and 9 still commit an explicit no-op; no
4h lifecycle rows are fabricated. Any exception rolls back the entire list.
The outer progression boundary then terminalizes the attempt with the exact
first cause in a separate transaction, leaving `ELIGIBLE_PENDING_HANDOFF`
truth visible and the 1h predecessors unchanged.

Uniqueness constraints on attempt, slot/cycle successor windows, step keys,
Scheduler ownership and campaign work prevent duplicates. An exact committed
handoff may be verified idempotently, but no restart path may invoke creation
automatically. Partial legacy or conflicting state fails closed for operator
review.

## 10. Crash and interruption contract

| Crash point | Durable observation | Classification and permitted behavior |
| --- | --- | --- |
| Before attempt persistence | no standard 1h handoff has committed under the new contract | **safely pending**; if a required/terminal 1h graph exists without an attempt, report **interrupted/ambiguous**, never complete |
| After attempt exists, before eligibility completes | `WAITING_FOR_PREDECESSORS` with exact active peer, or durable `EVALUATING` | waiting on genuinely active peer is **safely pending**; stopped ownership with `EVALUATING` or terminal predecessors is **interrupted/ambiguous requiring review** |
| After eligibility, before handoff | `ELIGIBILITY_COMPLETE` plus exact eligible rows and no 4h graph | **safely pending**, explicitly “eligible but not created”; no automatic handoff/retry |
| During atomic handoff | SQLite yields the prior eligibility state after rollback or the complete committed graph | **safely pending** after rollback or committed after success; an uninspectable DB outcome is **interrupted/ambiguous requiring review** |
| After commit, before first claim | complete manifest/windows/steps/jobs/work and `HANDOFF_COMMITTED` | **safely pending**; Central Scheduler remains the only possible claimant |
| During claimed 4h work | exact step/job/work running and window collecting/close-pending | graceful fault is **terminal** through existing paths; abrupt loss is **interrupted/ambiguous requiring review** |
| After provider request, before terminal response persistence | durable request-only evidence or source terminal evidence with active execution rows | **interrupted/ambiguous requiring review**; pre-close `UNKNOWN_INTERRUPTED_AFTER_REQUEST` remains authoritative where applicable |
| After 4h terminal persistence, before accounting/report sync | exact terminal step/job/work/window/slot truth | execution is **terminal**; a later read-only report sync may observe it, but no lifecycle restart/successor is allowed |

No state authorizes automatic retry, resume, rerun, restart, successor, or
recovery. An operator-approved recovery lane may inspect or terminalize an
ambiguous attempt; this design grants no such invocation.

## 11. Accounting and reporting contract

One shared read-side derivation must serve the Standard-4H terminal validator,
full-run accounting, final campaign report and terminal summary.

For each token it reports exactly one of:

- `NEVER_ELIGIBLE` / `INELIGIBLE` with exact reasons;
- `WAITING_FOR_PROGRESSION_EVALUATION`;
- `ELIGIBLE_NOT_CREATED`;
- `CREATED_PENDING`;
- `RUNNING`;
- `SUCCEEDED`;
- `FAILED`;
- `CANCELLED`; or
- `INTERRUPTED_AMBIGUOUS`.

The aggregate is complete only when:

- an explicit `HANDOFF_COMMITTED` zero-token no-op has two ineligible rows; or
- every eligible `HANDOFF_CREATED` token has the exact terminal 4h graph and
  every ineligible token has a complete disposition.

If Standard-4H was required and its progression attempt is absent,
`EVALUATING` is stranded, an eligible row lacks handoff, or created rows are
partial, both validator and accounting return incomplete/ambiguous. Absence can
be `NOT_APPLICABLE` only when the immutable run configuration says
Standard-4H was not required. It is never inferred from zero 4h rows.

Reports expose the exact attempt ID, token dispositions, authority evidence,
primary and secondary faults, and derived 4h state. This does not repair the
separate Lane-4 Cycle-2 reporting/projection debt.

## 12. Schema and migration assessment

A schema change is required. A future migration, expected to be the next
canonical migration (currently `061`), must design and create:

- `printer_memory_factory_standard_4h_progression_attempts`; and
- `printer_memory_factory_standard_4h_progression_tokens`.

The parent contains exact campaign/configuration/campaign-run/factory-run/cycle
identity, state/timestamps, immutable authority evidence, first terminal cause
and the validated primary/secondary fault envelope. The child contains the
exact slot/token/mint/pair/lifecycle/queue/lane/predecessor identities,
disposition/reasons/evidence, optional successor 4h window, and token-local
first-cause envelope.

The migration must add composite foreign keys, one-attempt-per-cycle and
one-row-per-attempt/slot uniqueness, state/cause consistency checks, JSON
validity checks, immutable-identity/primary/terminal triggers, and indexes for
campaign-run/cycle and attempt/disposition reads. A transition out of waiting
must verify the exact two-row set in production and by read-back; SQLite cannot
express that cross-row cardinality with a simple row check.

No historical campaign is backfilled by inference. A historical standard run
with terminal 1h truth but no progression aggregate remains explicitly legacy
ambiguous/incomplete. The migration itself creates no campaign rows and
activates no capability.

## 13. Expected future production files

The narrow implementation is expected to touch only the following production
areas, plus focused tests:

- new `migrations/061_*standard_4h_progression*.sql`;
- new `src/printer_v1/operator_cli/standard_4h_progression.py` for the aggregate,
  authority reads, transitions and shared status derivation;
- `operational_selective_1h.py` / `campaign_ownership.py` to create the attempt
  and exact two token rows within the standard first-hour handoff transaction;
- `one_command_15m_factory.py` to move progression outside the predecessor
  handler, invoke it after every 1h terminal outcome, use its budget/status
  derivation, and preserve primary faults;
- `operational_standard_4h.py` to stop synthesizing inputs and delegate to the
  durable coordinator;
- `one_token_4h_runtime.py` to consume authoritative token dispositions and
  include their transitions in the existing handoff transaction;
- `campaign_full_run_accounting.py`, `final_campaign_report.py`, and
  `unified_terminal_closure.py` to consume the one shared status/fault contract;
  and
- runtime schema-readiness checks that explicitly enumerate required tables.

`cadence_authority.py`, Scheduler selection/claim modules, Source Governor,
cadence/evidence policy, and provider adapters are consumers or preserved
authorities, not expected behavior-change targets.

## 14. Minimum implementation and proof plan

The separate implementation lane should proceed narrowly:

1. Add the migration and aggregate module with identity/state/immutability
   checks.
2. Create the attempt with standard 1h handoff; invoke progression after all
   1h terminal outcomes outside the predecessor exception handler.
3. Replace synthesized barrier inputs with exact existing authority reads and
   persist the resulting evidence/dispositions.
4. Extend the existing atomic planner transaction and switch validator,
   accounting and reporting to one status derivation.
5. Integrate first-primary/secondary fault propagation without altering
   Scheduler or Source Governor policy.

Minimum focused proof injects underlying production conditions, not expected
classifications:

- make a real authority read or handoff write fail after committed 1h success;
  prove the predecessor step/job/work/window remains succeeded;
- terminalize one exact 1h predecessor failed and cancelled in separate cases;
  prove the eligible peer receives its lawful 4h plan;
- mutate underlying campaign state, lease expiry/cancellation, DB binding,
  budget usage and queue identity in focused disposable databases; prove the
  persisted evidence comes from those owners and the opposite healthy case
  reaches eligibility;
- stop after `ELIGIBILITY_COMPLETE`; prove both terminal consumers report
  `ELIGIBLE_NOT_CREATED`, never complete;
- inject a progression fault followed by a cleanup/report fault; prove the
  first remains primary and the latter is secondary;
- interrupt after `EVALUATING` and after a request-only source record; prove
  ambiguous/review truth, not success;
- prove atomic 0/1/2 subsets, transaction rollback, exact committed read-back,
  and no duplicate 4h plan on an exact verification/replay;
- run the nearest Lane-2 selector/deadline/source-unit contract tests unchanged
  to prove category-first ordering, deadlines, fairness, one unit per claim,
  reselection and Source Governor ownership remain intact; and
- statically assert no Cycle 3, 12h/24h, retrieval or financial row/surface is
  created or enabled.

No broad regression suite is specified. Migration checks, the progression
contract tests, affected 1h->4h integration/accounting/report tests, nearest
Lane-2 locks, compilation and diff checks are minimum sufficient verification.

## 15. Explicit unchanged and locked surfaces

Implementation must not change:

- Central Scheduler selection or claim authority;
- Source Governor source authority or provider composition;
- Lane-2 category-first ordering, within-category deadlines, exact deadline
  provenance, token/cycle fairness, pre-close fork/join, one governed source
  unit per claim, reselection after each unit, evidence-time boundaries,
  degraded-context success, or technical-context fail-closed behavior;
- Standard-4H evidence quality, clean/dirty/do-not-train, safety, freshness,
  provenance or continuity gates;
- the consumed 4/2/2 authorization or any campaign/runtime authority;
- automatic retry, resume, rerun, restart, successor or recovery behavior;
- Lane-4 multi-cycle accounting/reporting debt;
- `WINDOW_5M_MICRO_EVENT` support-only status; or
- Cycle 3, `WINDOW_12H`, `WINDOW_24H`, retrieval, BUY/SELL/HOLD, positions,
  trade events, paper audits, PnL, wallets/private keys/signing/real funds/live
  execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings
  or vectors.

## 16. Implementation-readiness conclusion

Every new runtime concept has a real producer, durable owner, named consumer,
terminal behavior and focused proof boundary. The schema extension is
necessary rather than decorative; the current lawful Scheduler-owned,
Source-Governed Standard-4H plan and Lane-2 contracts remain in place.

Exact next permitted action:

```text
LANE 3:
Post-1H Standard-4H Progression + Fault Preservation
NARROW IMPLEMENTATION + FOCUSED PROOF ONLY.
```

This verdict does not authorize a campaign, replay, recovery, Cycle 3, a later
lane, or any locked capability.

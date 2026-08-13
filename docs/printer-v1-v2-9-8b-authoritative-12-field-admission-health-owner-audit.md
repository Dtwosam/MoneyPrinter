# Printer V1 V2-9.8B Authoritative 12-Field Admission-Health Owner Audit

## Verdict

`V2_9_8B_12_FIELD_ADMISSION_HEALTH_OWNER_AUDIT_PASS_READY_FOR_TDD_IMPLEMENTATION`

All twelve `MultiCycleAdmissionHealth` fields now have an existing authoritative owner or an exact owner-backed read-only composition path. No remaining field requires invented policy, copied ceilings, a new Scheduler, a second source-budget model, historical DB mutation, source execution, or a synthetic write probe.

This is an owner/readiness audit only. It does **not** mean the 12-field projection is implemented, and it does not establish that the live operational campaign is currently healthy. Four field groups still require narrow read-only adapters/factoring so the existing owner facts can be composed into one proof-only `MultiCycleAdmissionHealth` projection.

## Baseline

Branch:

`agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`

Audit baseline:

`9fcc2ca1a687dac44c32309e89781299339b1248`

Relevant existing design:

`docs/printer-v1-v2-9-8b-admission-health-and-wake-disposition-design.md`

Completed prerequisite:

`docs/printer-v1-v2-9-8b-source-free-discovery-capacity-authority-closeout.md`

The source-free discovery-capacity prerequisite closed the two owner gaps that previously blocked this audit:

- `provider_budgets_available`
- `discovery_capacity_available`

Public `TOKEN_CAPACITY` remains 2. The bounded proof shape remains exactly four through-4h tokens, two simultaneous exact-two-token cycles, and two total admissions.

## Audit rule

An owner is sufficient for this audit only when the field can be derived from committed machine-readable state or an existing canonical calculation without:

- default/all-true health assumptions;
- copied numeric ceilings;
- documentation-prose parsing;
- source fetching;
- Scheduler mutation;
- DB mutation;
- lease acquisition/renewal;
- callback execution;
- admission persistence;
- polling/backoff;
- a new scoring/ranking/confidence model.

`MultiCycleAdmissionHealth()` defaults are compatibility defaults only and are forbidden as runtime admission authority.

## 12-field authority map

### 1. `source_budget_available`

**Status:** `OWNER_EXISTS__READ_ONLY_FORECAST_ADAPTER_REQUIRED`

Authoritative owners:

- `one_token_4h_runtime.standard_campaign_lifecycle_budget(...)` and `cumulative_lifecycle_budget(...)` own the cadence-derived request components and request ceilings;
- `operational_standard_4h.standard_four_hour_capacity_contract()` projects the public exact-two-token worst-case envelope from that canonical arithmetic;
- `multi_cycle_memory_growth.scaled_standard_four_hour_capacity_contract(4)` derives the four-token simultaneous envelope from the exact two-token owner;
- `one_command_15m_factory._enforce_budgets_before_step(...)`, `_projected_requests_for_step(...)`, and run-local request accounting are the canonical execution-time hard-budget enforcement path;
- Source Governor/governed provider-reaching accounting remains authoritative for actual source-attempt attribution.

Audit conclusion:

The numeric and consumption owners exist. The health projection must factor a pure read-only forecast from the same arithmetic so it can answer whether fresh admission preserves the existing total source envelope. It must not call the mutating execution path or duplicate its formulas.

No new design is required.

### 2. `provider_budgets_available`

**Status:** `EXACT_OWNER_COMPLETE`

Authoritative owner:

`src/printer_v1/operator_cli/source_free_discovery_provider_capacity.py`

`compose_later_cycle_discovery_capacity(...)` uses:

- `C` from `recent_consumed_provider_attempts(...)`;
- `R` from the validated source-free manifest;
- `L` from `SOURCE_REGISTRY[source].default_rate_limit_per_minute`;
- the canonical inclusive 60-second window;
- persisted request timestamps only for exact package-ready boundaries.

Ambiguous attempt evidence fails closed and supplies no synthetic recheck time.

### 3. `scheduler_budget_available`

**Status:** `OWNER_EXISTS__READ_ONLY_CAPACITY_ADAPTER_REQUIRED`

Authoritative owners:

- Central Scheduler durable rows;
- exact factory-run Scheduler-job correspondence in `printer_memory_factory_run_steps`;
- stage-scoped `printer_memory_factory_campaign_scheduler_work` ownership;
- `campaign_active_work.campaign_scoped_job_ids(...)` / `campaign_active_work_report(...)` for campaign-attributable Scheduler work;
- `standard_four_hour_capacity_contract()` plus `scaled_standard_four_hour_capacity_contract(4)` for the derived Scheduler outer envelope;
- existing factory budget enforcement/reporting for actual Scheduler-row consumption.

Audit conclusion:

The health implementation needs only a narrow read-only adapter that calculates current attributable Scheduler consumption and remaining admission capacity using the existing derived envelope. It must not enqueue, claim, cancel, or copy the Scheduler ceiling.

### 4. `scheduler_due_work_healthy`

**Status:** `EXACT_OWNER_EXISTS__NARROW_CLASSIFIER_REQUIRED`

Authoritative owners:

- Central Scheduler row state/lock state;
- stage-scoped campaign Scheduler ownership;
- factory run-step Scheduler correspondence;
- `campaign_active_work_report(...)` and exact campaign job attribution.

`campaign_active_work` already includes PENDING, RUNNING, COOLDOWN, locked work, discovery-owned jobs, campaign Scheduler work, and pre-lifecycle refresh waits. It explicitly performs no source call, Scheduler mutation, or write.

Derivation requirement:

A due/claimed attributable job can be healthy and must receive priority over fresh admission. The field is false only when due/claimed work has ownership drift, orphaning, contradictory lock/state, or another existing Scheduler integrity defect.

The classifier may compose the existing rows/reports but cannot become a second Scheduler implementation.

### 5. `close_reserve_available`

**Status:** `OWNER_EXISTS__PURE_RESERVE_FORECAST_REQUIRED`

Authoritative owners:

- `one_command_15m_factory._projected_requests_for_step(...)`;
- `one_command_15m_factory._lifecycle_reservation_records_for_step(...)`;
- `one_command_15m_factory._enforce_budgets_before_step(...)`;
- `one_token_4h_runtime.require_projected_capacity(...)`;
- cadence/runtime request arithmetic from `standard_campaign_lifecycle_budget(...)`;
- measured transport/lifecycle reservation constants already consumed by the factory.

Audit conclusion:

The current factory proves capacity immediately before lifecycle work. The health projection needs the same owner facts exposed/factored as a pure forecast that protects every already-owed mandatory close before a fresh exact two-token admission.

Do not copy close-request counts or reservation arithmetic into a second policy.

### 6. `campaign_supervision_healthy`

**Status:** `EXACT_OWNER_COMPLETE`

Authoritative owner:

`src/printer_v1/operator_cli/campaign_supervision.py`

The module owns persisted campaign supervision and provides read-only inspection using SQLite `mode=ro` / `PRAGMA query_only=ON`. Supervision state, heartbeat ownership, cancellation state, and terminal supervision defects are durable.

The health projection may inspect this state only. It must not call renewal, acquisition, cancellation mutation, or terminal cleanup.

### 7. `lease_healthy`

**Status:** `EXACT_OWNER_COMPLETE`

Authoritative owner:

`campaign_supervision.py`

The read-side supervision projection already carries persisted `heartbeat_at`, `lease_expires_at`, exact lock ownership, `lease_expired`, and `new_child_work_allowed` semantics.

Expired, missing, mismatched, ambiguous, or conflicting lease ownership is unhealthy. Admission health must never acquire or renew the lease.

`lease_expires_at` is an existing owner-backed future time boundary and may be carried as health evidence when useful; it is not a polling interval or permission to extend the lease.

### 8. `db_healthy`

**Status:** `EXACT_OWNERS_EXIST__READ_ONLY_COMPOSITION_REQUIRED`

Authoritative owners:

- `proof_db_schema_readiness.validate_runtime_schema_connection(...)` for canonical migration/schema/integrity/foreign-key readiness;
- `operational_database_target_binding.py` for immutable target path, SHA/migration expectation, authorization/application-marker facts, ownership identities, and reuse constraints;
- persisted campaign/configuration/run/cycle/factory identities from the coordinator.

The projection must validate read-side schema/binding/ownership against the already-authorized DB target. It must not perform a synthetic write probe.

Any missing, mismatched, ambiguous, or unreadable binding fails closed.

### 9. `shared_terminal_condition`

**Status:** `EXACT_OWNERS_EXIST__READ_ONLY_TERMINAL_PROJECTION_REQUIRED`

Authoritative owners:

- persisted campaign/run/cycle/factory-run terminal states;
- immutable first-terminal-cause law in the existing campaign ownership/terminal path;
- `campaign_active_work_report(...)` for attributable active-work reconciliation;
- `unified_terminal_closure.py` for the canonical terminal-state mapping/reconciliation law.

The health projection must **read**, not invoke, terminal reconciliation.

A shared terminal condition is true when existing persisted authority already forbids fresh admission. Historical terminal state and zero attributable active work must reconcile consistently; contradictory terminal/active-work evidence fails closed rather than being treated as healthy.

### 10. `cancellation_requested`

**Status:** `EXACT_OWNER_COMPLETE`

Authoritative owners:

- persisted supervision `cancellation_requested_at` / cancellation state;
- persisted campaign/run `STOP_REQUESTED` state already consumed by the multi-cycle coordinator.

The projection may observe cancellation only. It may not create, clear, acknowledge, or terminalize it.

### 11. `discovery_capacity_available`

**Status:** `EXACT_OWNER_COMPLETE`

Authoritative owner:

`source_free_discovery_provider_capacity.compose_later_cycle_discovery_capacity(...)`

The field is the source-free action-shape validity result:

- exact two-token manifest;
- owner-derived request requirements;
- valid registered free/Solana request kinds;
- no prohibited/paid source;
- representable bounded discovery action.

It remains deliberately separate from `provider_budgets_available`.

### 12. `protected_work_capacity_available`

**Status:** `OWNER_EXISTS__PURE_FUTURE_WORK_FORECAST_REQUIRED`

Authoritative owners:

- `standard_campaign_lifecycle_budget(...)` and `standard_four_hour_capacity_contract()`;
- `scaled_standard_four_hour_capacity_contract(4)`;
- current factory run-step and campaign ownership state;
- factory hard-budget/reservation owner;
- Central Scheduler capacity/ownership state;
- already-owed 15m/1h/4h lifecycle work and mandatory close reservations.

Audit conclusion:

The projection needs a pure read-only forecast from the existing lifecycle-budget owner that proves fresh admission cannot consume capacity owed to existing tokens. This must reuse the same cadence-derived request/Scheduler components and reservation law as the factory.

Do not approximate future work from wall-clock duration or copy the 236/117-style public numbers into a new formula.

## Adapter/factoring work still required

The audit found **no missing authority**, but the implementation needs these focused read-only compositions:

1. source-envelope forecast;
2. Scheduler remaining-capacity + due-work integrity projection;
3. close/protected-future-work reserve forecast;
4. DB/shared-terminal composition.

These adapters must be thin: expose existing owner arithmetic/state, not redefine it.

## Rearm / reevaluation evidence available to the health projection

This lane does not implement admission disposition/rearm, but the health result may carry existing owner-backed evidence for the later disposition lane.

Authoritative time evidence currently available:

- provider `recheck_at` from the completed source-free provider-capacity owner;
- lease `lease_expires_at` from persisted campaign supervision.

Authoritative state-change evidence:

- Scheduler/lifecycle completion or ownership-state change;
- close/protected-work release after existing lifecycle work completes;
- supervision/cancellation/terminal-state transition;
- DB/binding state change, which is fail-closed rather than polled.

For Scheduler, close reserve, protected work, and similar capacity fields, if no existing owner names an exact future timestamp, the health projection should carry `recheck_on_lifecycle_change=True` rather than inventing a timer.

Minimum admission spacing remains controller/session authority and is not moved into the health projection.

## TDD implementation boundary

The next implementation lane is only the proof-side read-only 12-field projection.

Preferred immutable result semantics:

```text
AdmissionHealthProjection
  health: MultiCycleAdmissionHealth
  recheck_at: datetime | None
  recheck_on_lifecycle_change: bool
  reasons/evidence
```

The implementation must construct every boolean from current owner evidence. It must never use `MultiCycleAdmissionHealth()` as a healthy shortcut.

Minimum focused proof must show:

1. all twelve fields are populated from owner evidence;
2. each field can turn false when its owner evidence changes;
3. missing/ambiguous owner evidence fails closed;
4. provider and discovery fields consume the completed source-free authority;
5. source/Scheduler/close/protected forecasts reuse existing derived budget owners;
6. healthy due lifecycle work is distinguished from Scheduler ownership drift;
7. lease/supervision are read-only and never renewed/acquired;
8. DB health uses schema/binding reads with no synthetic write;
9. terminal/cancellation reads create no terminal mutation;
10. provider `recheck_at` is preserved when authoritative;
11. lifecycle-change reevaluation is used where no exact time owner exists;
12. zero source requests, Scheduler mutation, DB mutation, callback, admission, runtime, or authorization activity.

Use risk-based focused tests only. A broad suite is not required for this implementation seam.

## Money-usefulness contribution

This audit removes the last policy-authority uncertainty before Printer can decide whether a second exact two-token cycle is safe to consider. It ensures the admission gate protects provider budgets, total source/Scheduler envelopes, existing token closes and future lifecycle work, supervision/lease ownership, and terminal integrity before the system spends discovery capacity on additional tokens.

## What this lane improves

- proves every admission-health boolean can be grounded in committed owner state;
- prevents healthy-default admission;
- prevents duplicate budget/Scheduler policy;
- preserves existing tokens' 15m/1h/4h work before adding a second cycle;
- provides a bounded path back to the four-token proof integration sequence.

## What this lane still does not unlock

This audit does not unlock:

- admission disposition/rearm;
- later-cycle discovery callback execution;
- cycle-2 persistence/scheduling;
- factory-loop integration;
- source fetching;
- memory generation;
- runtime/proof authorization;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- Factoring the budget forecasts incorrectly could create a second arithmetic owner; implementation tests must compare against the existing factory/runtime calculations.
- `campaign_active_work_report(...)` reports active work, but `scheduler_due_work_healthy` still needs a narrow integrity classifier so healthy due work is not mistaken for unhealthy capacity.
- Shared-terminal projection must not call the mutating terminal reconciler.
- A lease expiry timestamp is a safety boundary, not a renewal/retry schedule.
- Missing owner evidence must remain false/blocked even when that causes conservative deferral.
- The implementation must keep `provider_budgets_available` separate from `discovery_capacity_available` and from the total source-budget envelope.

## Closeout

`V2_9_8B_12_FIELD_ADMISSION_HEALTH_OWNER_AUDIT_PASS_READY_FOR_TDD_IMPLEMENTATION`

Correct next lane:

**TDD-implement the proof-only, read-only authoritative 12-field `MultiCycleAdmissionHealth` projection.**

Stop after that projection and its focused verification. Do not implement admission disposition/rearm in the same seam.

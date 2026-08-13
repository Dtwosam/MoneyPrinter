# Printer V1 V2-9.8B Admission Health and Wake Disposition Design

## Verdict

`V2_9_8B_ADMISSION_HEALTH_AND_WAKE_DISPOSITION_DESIGN_PASS_READY_FOR_FOCUSED_IMPLEMENTATION`

This design closes the two blockers found while attempting canonical four-token factory wake integration:

1. no authoritative read-only projection currently constructs `MultiCycleAdmissionHealth` from real committed owners; and
2. no final contract currently defines how a due `CYCLE_ADMISSION` wake is consumed or rearmed without busy-polling, lifecycle starvation, or an implicit retry policy.

The design does not authorize runtime or the four-token proof. It creates no source calls, Scheduler work, DB mutation, memory, authorization, retrieval, paper decision, position, trade, audit, PnL, 12h/24h activation, or six-token proof.

## Authority and baseline

Use the active Printer V1 source stack together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-python-builder-guide.md`
- `docs/printer-v1-v2-9-8b-four-token-bounded-capacity-proof-integration-design.md`

Immediate implementation baseline:

- branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- reviewed controller-readiness HEAD: `73b768ebe87cefcc551d3589892b76f136c72b92`
- read-only controller readiness: PASS
- canonical factory wake integration: blocked pending this design

The proof configuration remains exactly:

```text
configured through-4h tokens = 4
configured active cycles = 2
total cycle admissions = 2
per-cycle token capacity = 2
minimum admission spacing >= 300 seconds
standard-four-hour campaign only
```

Public `TOKEN_CAPACITY` remains 2.

## Design decision 1 - retain one health carrier, add one owner-backed read-only projection

`MultiCycleAdmissionHealth` remains the canonical gate carrier. Do not create a second boolean policy model and do not change its fields into scores, weights, ranks, or confidence values.

Add one focused proof-only projection layer in a later implementation seam. Its job is only to ask existing owners for current state and construct `MultiCycleAdmissionHealth` plus explicit rearm evidence.

Conceptually the projection returns:

```text
health: MultiCycleAdmissionHealth
recheck_at: optional authoritative future time
recheck_on_lifecycle_change: bool
blocking_reasons: exact reason codes/evidence
```

`recheck_at` is not a polling interval. It may exist only when an existing owner can name a real future boundary, such as an admission-spacing boundary or provider/budget refill boundary.

The projection must be side-effect free:

- no source request;
- no Scheduler enqueue/claim/cancel;
- no DB mutation;
- no lease mutation;
- no supervision mutation;
- no discovery execution;
- no lifecycle execution.

A missing or ambiguous owner answer fails closed. Default/all-true `MultiCycleAdmissionHealth()` is forbidden for four-token admission authority.

## Exact authority mapping

### `source_budget_available`

Canonical authority:

- Source Governor / governed source execution boundary;
- persisted governed source-request accounting (`printer_source_requests` and existing governed-attempt attribution);
- the derived simultaneous envelope from `scaled_standard_four_hour_capacity_contract(4)`.

Current gap:

There is no committed single read-only helper that answers whether another exact two-token discovery/lifecycle package can be admitted while preserving the existing source-request reserve.

Required prerequisite:

Add a narrow read-only Source-Governor/budget projection adapter that reports current attributable consumption against the existing derived contract. It must reuse the existing accounting owner and must not copy request ceilings into new constants.

Fail closed when attribution is incomplete, ambiguous, or cannot preserve the required reserve.

### `provider_budgets_available`

Canonical authority:

- existing provider-specific measured/governed transport budget owner;
- existing provider pacing/rate-ceiling state;
- provider ceilings already enforced by the standard-four-hour path.

Current gap:

No committed aggregate read-only helper projects whether all providers needed by an additional exact pair retain lawful capacity.

Required prerequisite:

Expose a read-only provider-capacity snapshot from the existing transport/budget owner. If a provider gate is time-based, the owner may return its exact next lawful boundary; otherwise no synthetic retry time is allowed.

Fail closed on unknown provider capacity.

### `scheduler_budget_available`

Canonical authority:

- Central Scheduler;
- existing factory-run Scheduler rows;
- stage-scoped `printer_memory_factory_campaign_scheduler_work` ownership;
- the derived Scheduler envelope from `scaled_standard_four_hour_capacity_contract(4)`.

Current gap:

There is no single read-only admission-capacity projection that proves a second exact pair can be scheduled while preserving existing due and mandatory work.

Required prerequisite:

Add a read-only Scheduler-capacity adapter owned by the Central Scheduler boundary. It must use existing job/ownership state and derived ceilings rather than independently counting against copied magic numbers.

Fail closed if Scheduler ownership or remaining capacity is ambiguous.

### `scheduler_due_work_healthy`

Canonical authority:

- Central Scheduler due-work state;
- factory `printer_memory_factory_run_steps` Scheduler correspondence;
- stage-scoped campaign Scheduler ownership;
- existing campaign active-work reconciliation/reporting.

Derivation:

True only when all currently due/claimed attributable lifecycle work is internally consistent and no Scheduler ownership defect requires safe-stop or repair.

A healthy due job does not block forever; it instead receives priority over fresh admission. An ambiguous/orphan/ownership-drift condition makes this field false.

Required adapter:

A narrow read-only projection may compose existing Scheduler/ownership reports, but it must not become a second Scheduler implementation.

### `close_reserve_available`

Canonical authority:

- existing factory hard-budget enforcement;
- existing lifecycle reservation accounting, including `_enforce_budgets_before_step(...)` and `_lifecycle_reservation_records_for_step(...)`;
- standard-four-hour derived capacity authority.

Current gap:

Current code enforces reserve immediately before lifecycle work but does not expose a read-only pre-admission forecast for the additional pair.

Required prerequisite:

Factor or expose a read-only forecast from the same budget/reservation owner that answers whether admitting cycle 2 still preserves every mandatory close operation already owed plus the new pair's required close reserve.

Do not duplicate the reservation arithmetic.

### `campaign_supervision_healthy`

Canonical authority:

- `src/printer_v1/operator_cli/campaign_supervision.py`;
- persisted campaign supervision state and existing supervision inspection law.

Derivation:

True only while the one authoritative campaign supervision execution remains in a state that permits continued work and has no terminal supervision defect.

No new supervision state is introduced.

### `lease_healthy`

Canonical authority:

- existing operational campaign lease/heartbeat ownership in `campaign_supervision.py` and its committed safe-stop/recovery law.

Derivation:

True only when the current campaign still owns its valid lease/heartbeat authority. Expired, lost, ambiguous, or conflicting ownership is false and triggers the existing safe-stop path.

Admission health must never renew or acquire a lease.

### `db_healthy`

Canonical authority:

- the existing authoritative persistent DB binding and schema-readiness checks;
- the current factory SQLite connection and campaign/factory ownership invariants;
- existing SQLite/heartbeat concurrency law.

Derivation:

True only when the authoritative DB target is still the expected DB, required schema/ownership rows remain readable, and the read-side projection encounters no DB/identity/concurrency defect.

Do not perform a synthetic write to prove DB health.

### `shared_terminal_condition`

Canonical authority:

- persisted campaign, campaign-run, cycle and factory-run state;
- existing campaign active-work reporting/reconciliation;
- first-terminal-cause and shared terminalization law.

Derivation:

True when a shared terminal cause already forbids any new cycle admission, including cancellation, terminal campaign/run/factory state, or another shared terminal condition recognized by existing owners.

This is a stop gate, not a defer gate.

### `cancellation_requested`

Canonical authority:

- the existing `cancellation_probe` / supervision cancellation path used by the canonical factory.

Derivation:

True only from the existing cancellation owner. The admission projection may read cancellation state but may not create or clear it.

### `discovery_capacity_available`

Canonical authority:

- the existing authoritative operational discovery/selection owner;
- Source Governor;
- Central Scheduler;
- the current bounded discovery request/Scheduler attribution contract.

Current gap:

The later-cycle discovery callback is still intentionally fail-closed and there is no read-only capacity projection proving that one additional exact two-token discovery action can begin safely.

Required prerequisite:

The later callback implementation must expose or reuse a read-only capacity check from the existing discovery owner. This field becomes true only when that owner can accept exactly one cycle-2 discovery action under current source/Scheduler capacity.

No parallel polling/fetch loop is allowed.

### `protected_work_capacity_available`

Canonical authority:

- standard-four-hour derived budget authority;
- existing lifecycle reservation/hard-ceiling owner;
- Central Scheduler capacity law;
- protected future 1h/4h and mandatory-close work already owed by admitted tokens.

Current gap:

There is no committed read-only helper that projects the future protected-work reserve for an additional pair.

Required prerequisite:

Expose a read-only forecast from the same budget/reservation owner used by lifecycle enforcement. The forecast must prove that admitting the new pair does not consume capacity reserved for already-admitted healthy tokens or their mandatory closes.

No new independent arithmetic or copied ceiling is permitted.

## Design decision 2 - separate readiness reevaluation from an admission attempt

A readiness reevaluation is not an admission retry.

Before the later-cycle discovery callback is invoked, the system may reevaluate health only when an authoritative event or time boundary occurs. No source work, discovery attempt, cycle persistence, or Scheduler admission work has happened yet.

The first invocation of the later-cycle discovery callback for cycle 2 is the one real admission attempt.

Once that callback is invoked:

- it may return exactly two validated targets plus existing handoff evidence; or
- it may return an honest no-pair/defer/block result.

There is no second callback invocation for the same cycle-2 proof opportunity. No automatic retry, restart, resume, successor, or lowered eligibility is allowed.

## Design decision 3 - authoritative rearm boundaries only

A deferred readiness gate may rearm only from one of these boundaries:

1. the persisted 300-second admission-spacing boundary;
2. an exact future boundary returned by an existing capacity owner, such as a provider or governed budget refill boundary;
3. completion/terminalization of canonical lifecycle work that can change capacity, followed by one fresh read-only health projection;
4. a supervision/lease/cancellation state transition already surfaced by existing supervision law;
5. the bounded proof deadline.

There is no arbitrary `sleep(1)`, retry interval, poll cadence, backoff loop, or background thread/process.

If no owner can name a future boundary and there is no pending lifecycle work capable of changing the blocked gate, the four-token proof cannot lawfully wait for an unknown improvement. It must end as an honest blocked/deferred capacity outcome.

## Design decision 4 - one loop priority law

The canonical factory retains one loop.

At each loop boundary, priority is:

```text
1. cancellation / lease / DB / shared-terminal safe-stop
2. already-due mandatory or lifecycle Scheduler work
3. proof deadline
4. due cycle-admission readiness evaluation
5. sleep until the earliest authoritative future boundary
```

If lifecycle work and admission are due at the same instant, lifecycle work wins.

After a lifecycle step completes or terminalizes, admission health may be recomputed once because that event can legitimately free or consume capacity.

Healthy cycle-1 work is never cancelled, delayed, rewritten, or terminalized merely because cycle 2 is deferred or blocked.

## State / decision table

| State / decision | Factory disposition | Rearm | Callback? |
|---|---|---|---|
| `ADMIT_TWO_TOKEN_CYCLE`, all health gates valid, no higher-priority due lifecycle work | Begin the one cycle-2 admission attempt | None before attempt | Exactly once |
| `DEFER` because minimum spacing has not elapsed | Keep cycle 1 running | Persisted spacing boundary | No |
| `DEFER` because source/provider capacity is unavailable and owner provides `next_available_at` | Keep cycle 1 running | Exact owner-provided time, lifecycle change, or deadline whichever is earlier | No |
| `DEFER` because Scheduler/close/protected-work/discovery capacity is unavailable | Keep cycle 1 running | Relevant lifecycle/Scheduler state change if one exists; otherwise terminal blocked | No |
| `BLOCKED` | Existing shared safe-stop / blocked proof outcome | None | No |
| `DRAIN` | No fresh admission; continue already-admitted lifecycle work to lawful drain | Existing lifecycle due boundaries | No |
| `COMPLETE` | No fresh admission; proceed to shared terminal closeout when existing work is terminal | None | No |
| cancellation requested | Existing cancellation safe-stop | None | No |
| lease unhealthy | Existing lease-loss safe-stop | None | No |
| DB unhealthy | Existing DB safe-stop | None | No |
| shared terminal condition | Existing first-terminal-cause path | None | No |
| lifecycle work and admission due together | Execute lifecycle work first, then recompute health once | Post-lifecycle state change | No until a later valid evaluation |
| no lifecycle work pending and valid future owner boundary exists | Cancellation-aware sleep to that exact boundary | That boundary | No |
| no lifecycle work pending and no authoritative future boundary exists | Honest blocked/deferred capacity terminal outcome | None | No |
| proof deadline reached | Bounded proof stop; no fresh admission | None | No |

## Design decision 5 - admission attempt and later-cycle discovery

When every gate passes and no higher-priority lifecycle work is due, the single loop may enter the one cycle-2 admission attempt.

The sequence is:

```text
fresh read-only health projection
-> controller returns ADMIT_TWO_TOKEN_CYCLE / CYCLE_ADMISSION
-> recheck cancellation, lease, DB, deadline and due lifecycle priority
-> invoke authoritative owner's later-cycle discovery callback exactly once
-> callback returns exact pair + evidence OR honest no-pair/defer/block
-> only exact valid pair may proceed to persisted two-token cycle admission
```

The callback remains the same authoritative operational discovery/selection owner. It must use the same Source Governor and Central Scheduler and must not create a second polling/fetch loop.

If callback execution has begun and returns no eligible exact pair, a capacity/source block, or another honest non-success result, the proof does not invoke it again.

A later implementation lane must bind the callback to a durable attributable attempt identity using existing campaign/Scheduler ownership. If current persisted ownership cannot represent the pre-admission discovery attempt without ambiguity, that callback lane must stop and design the minimum ownership repair before runtime activation. Do not emulate durability with an in-memory retry counter and do not widen the schema without a proven blocker.

## Design decision 6 - exact pair persistence remains separate

This design does not move `admit_two_token_cycle(...)` into the readiness controller.

Only after the authoritative callback returns exactly two validated fresh targets may the existing multi-cycle coordinator perform the atomic cycle-2/token-slot admission.

The persistence call must still re-evaluate canonical admission state transactionally. If the state changed between read-side readiness and persistence, it fails/defer closes honestly rather than overriding the coordinator.

No single-token admission is permitted.

## Design decision 7 - proof deadline authority

The controller's wall-clock `proof_deadline` is derived from the same lifecycle-start boundary used by the canonical factory plus its existing bounded `total_duration_seconds` authority.

The factory's monotonic elapsed-time stop remains authoritative for execution. The wall-clock deadline exists only to select the same bounded wake boundary and must not extend runtime.

## Implementation sequence

### Step 1 - TDD authoritative admission-health projection

Implement the proof-only read-side adapter and any minimum owner-local read-only helpers required to populate all twelve `MultiCycleAdmissionHealth` fields.

Tests must prove each false gate independently, evidence attribution, zero writes, no source/Scheduler execution, and no default/all-true fallback.

Stop if any field still requires invented authority.

### Step 2 - TDD admission disposition / rearm contract

Implement a pure/small decision helper that consumes controller readiness, projected health/rearm evidence, next due lifecycle boundary, and proof deadline.

It chooses only the dispositions in this design. Tests must prove no busy polling, lifecycle tie priority, no unknown-time retry, and honest block when no authoritative rearm exists.

### Step 3 - TDD later-cycle callback implementation

Bind the existing fail-closed callback to the same authoritative operational discovery/selection owner, Source Governor, and Central Scheduler.

Prove exactly one governed cycle-2 attempt, exact context propagation, no second loop, and honest no-pair/block handling.

Do not persist cycle 2 in this step unless the callback's existing ownership contract requires a separately approved minimal prerequisite.

### Step 4 - TDD exact cycle-2 persistence and scheduling

After a validated exact pair exists, use the existing multi-cycle coordinator to admit exactly two slots under cycle 2 and add their opening jobs to the same authoritative factory run with cycle-aware namespace/ownership.

Re-check admission transactionally. No third cycle and no single-token admission.

### Step 5 - TDD canonical one-loop wake integration

Only after Steps 1-4 pass should the canonical factory loop consume the final health projection, rearm contract, callback and persistence path.

The public two-token path must remain behaviorally unchanged when the proof controller is absent.

## Money-usefulness contribution

This lane does not itself make a paper decision or earn simulated PnL. Its money-usefulness contribution is safer evidence throughput: Printer can eventually observe a second exact pair without sacrificing mandatory lifecycle closes, overloading sources/Scheduler capacity, or corrupting the first pair's memory. That increases the amount of trustworthy market evidence available to later explicitly approved retrieval and paper-decision lanes.

## What this improves

- Converts four-token admission health from implicit/default booleans into owner-backed evidence.
- Preserves Source Governor and Central Scheduler authority.
- Protects mandatory closes and future lifecycle work before adding capacity.
- Defines deterministic no-busy-poll rearm behavior.
- Separates harmless readiness reevaluation from the one real discovery/admission attempt.
- Preserves healthy cycle-1 work when cycle 2 cannot start.
- Keeps the four-token proof exact 4/2/2 and bounded.

## What this still does not unlock

This design does not unlock cycle-2 discovery, cycle-2 persistence, four-token runtime, a fresh proof authorization, a proof run, six-token execution, 12h/24h activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, or PnL.

## Proof / tests required before completion of the implementation sequence

Minimum focused proof must include:

1. every `MultiCycleAdmissionHealth` field projected from its real owner or fail-closed prerequisite;
2. no default/all-true operational projection;
3. read-side projection produces zero DB/source/Scheduler mutations;
4. source/provider/Scheduler/close/protected-work gates independently defer or block;
5. exact owner-provided time boundary rearms without polling;
6. no-boundary defer with no lifecycle-changing event becomes an honest blocked outcome;
7. lifecycle due work wins admission ties;
8. deadline bounds every wait;
9. callback is not invoked for spacing/defer/block/drain/complete/terminal states;
10. callback is invoked at most once for the one valid cycle-2 admission attempt;
11. no eligible pair does not cause a second callback or lowered eligibility;
12. transactional cycle admission rechecks state and admits exactly two slots only;
13. same campaign/run/factory ownership and cycle-aware Scheduler attribution remain exact;
14. public `TOKEN_CAPACITY == 2` and normal two-token behavior remain unchanged;
15. no 12h/24h, retrieval, paper decision, position, trade, audit or PnL capability delta.

Use risk-based verification: focused tests for each implementation seam, broader integration/lock coverage only at implementation closeout or before a bounded proof readiness review.

## Functionality Risks / Setbacks / Efficiency Blockers

### Risk - owner adapters accidentally become duplicate policy

Mitigation: adapters may expose current state/evidence only. They must reuse existing ceilings, ledgers and owner decisions instead of copying arithmetic or defining new thresholds.

### Risk - time-based capacity turns into hidden retries

Mitigation: wait only on an exact owner-produced future boundary. No generic backoff or periodic polling.

### Risk - lifecycle starvation

Mitigation: due/mandatory lifecycle work always outranks fresh admission, including equal-time ties; health is recomputed after the lifecycle event.

### Risk - callback invoked more than once

Mitigation: distinguish readiness reevaluation from the one real admission attempt. The callback implementation must bind one attributable attempt identity and terminalize honestly after no-pair/block.

### Risk - unknown capacity with no rearm source

Mitigation: fail closed. If no owner can prove current capacity or name a lawful future reevaluation boundary, do not wait indefinitely and do not guess; end as a blocked/deferred capacity proof.

### Efficiency blocker - multiple owners currently lack narrow read-only capacity views

The first implementation seam may require small owner-local introspection helpers for Source Governor/provider capacity, Scheduler capacity, and lifecycle close/protected-work reserve. This is expected and must remain read-only and narrowly scoped.

## Closeout

Design status:

`V2_9_8B_ADMISSION_HEALTH_AND_WAKE_DISPOSITION_DESIGN_PASS_READY_FOR_FOCUSED_IMPLEMENTATION`

Correct next lane:

`TDD authoritative MultiCycleAdmissionHealth projection`

Do not resume canonical factory wake integration until the admission-health projection and disposition/rearm seams pass focused proof.

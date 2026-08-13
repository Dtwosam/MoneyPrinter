# Printer V1 V2-9.8B — Durable Pre-Admission Discovery Attempt Ownership Design

## Verdict

`V2_9_8B_PRE_ADMISSION_DISCOVERY_ATTEMPT_OWNERSHIP_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`

This design resolves `BLOCKED_DURABLE_PRE_ADMISSION_DISCOVERY_ATTEMPT_OWNERSHIP_UNREPRESENTABLE` without pre-creating cycle 2 or weakening existing cycle-rooted discovery ownership.

It does not authorize live discovery, cycle-2 admission, factory-loop integration, proof authorization/runtime, 12h/24h, retrieval, decisions, positions, trades, audits, or PnL.

## 1. Authority and verified blocker

Use the active Printer V1 source stack plus:

- `docs/printer-v1-v2-9-8b-four-token-bounded-capacity-proof-integration-design.md`
- `docs/printer-v1-v2-9-8b-admission-health-and-wake-disposition-design.md`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/multi_cycle_campaign_coordinator.py`
- `src/printer_v1/scheduler/contracts.py`
- `src/printer_v1/scheduler/scheduler.py`
- migrations 034, 050, and 054.

Baseline before this design: `1e5e42623a925c84461ccbae0ca8df232f386786`.

Verified facts:

1. `CombinedPumpfunCampaignExecutor` requires the requested campaign cycle to exist before discovery.
2. `printer_discovery_batches` is FK-rooted in an existing campaign cycle.
3. combined discovery proceeds from selection into handoff/first-15m persistence rather than returning a pre-admission pair.
4. V2-stage `DISCOVERY_SELECTION` Scheduler ownership requires `factory_run_id IS NULL`.
5. migration 054 wait rows are ownership evidence only and cannot substitute for discovery work.
6. no durable pre-admission attempt/opportunity owner exists.
7. the Scheduler has `DISCOVERY_REFRESH` but no semantically correct job kind for one-shot pre-admission selection.

## 2. Preserve existing cycle-rooted ownership

Do not rebuild or relax migrations 034 or 050.

Do not create cycle 2 early merely to make existing foreign keys pass.

The repair is one additive pre-admission ownership path:

```text
campaign
 -> campaign run
 -> authoritative factory run
 -> proposed cycle ordinal/id
 -> one durable pre-admission attempt
 -> one Central Scheduler job
 -> governed discovery/gates/selection
 -> zero or exactly two frozen selected items
 -> later atomic cycle admission
```

The proposed cycle identity is evidence only until Step 4 succeeds.

## 3. Additive migration 055

Current repository state has no migration 055, so implement:

`migrations/055_pre_admission_discovery_attempt_ownership.sql`

Do not apply it to the authoritative operational DB in this implementation lane.

### 3.1 Attempt table

Add `printer_pre_admission_discovery_attempts` with:

- `attempt_id TEXT PRIMARY KEY`
- `campaign_id`
- `campaign_run_id`
- `configuration_id`
- `authoritative_factory_run_id`
- `proposed_cycle_ordinal`
- `proposed_cycle_id`
- `scheduler_job_id INTEGER NOT NULL UNIQUE`
- `cycle_cutoff`
- `evaluated_at`
- `selection_seed_identity`
- `attempt_state`
- `first_terminal_cause`
- `terminal_at`
- `consumed_cycle_id` nullable
- `consumed_at` nullable
- timestamps.

Required FKs bind existing campaign/run/configuration/factory/Scheduler owners. There is deliberately no pre-consumption FK to `printer_memory_factory_campaign_cycles`.

One-shot uniqueness:

```text
UNIQUE(campaign_id, campaign_run_id,
       authoritative_factory_run_id, proposed_cycle_ordinal)
```

For this proof, only proposed ordinal 2 is lawful.

### 3.2 Atomic attempt + Scheduler creation

Avoid a half-owned attempt.

Use one DB transaction and the existing Scheduler connection-aware API:

```text
BEGIN
 -> enqueue PRE_ADMISSION_DISCOVERY_SELECTION on the same connection
 -> obtain scheduler_job_id
 -> insert PLANNED attempt with scheduler_job_id NOT NULL
COMMIT
```

The Scheduler job name must deterministically include the exact `attempt_id`. The attempt row is the direct durable back-reference to the Scheduler job; do not infer ownership from request keys.

If either insert fails, rollback both.

### 3.3 States

Active:

- `PLANNED`
- `RUNNING`

Terminal/frozen:

- `PAIR_READY`
- `NO_PAIR`
- `BLOCKED`
- `FAILED`
- `CANCELLED`
- `CONSUMED`

Allowed transitions only:

```text
PLANNED -> RUNNING | CANCELLED | BLOCKED
RUNNING -> PAIR_READY | NO_PAIR | BLOCKED | FAILED | CANCELLED
PAIR_READY -> CONSUMED
```

No other terminal state can reopen. `CONSUMED` requires `consumed_cycle_id` and `consumed_at`. All terminal/frozen states require terminal cause/time.

## 4. Frozen exact-pair evidence

Add `printer_pre_admission_discovery_attempt_items`.

For `PAIR_READY`, exactly two immutable rows must exist with slot ordinals `{1,2}` and the existing handoff identity shape:

- token identity / row id
- mint identity
- pair identity / row id
- lifecycle identity
- canonical market/pool identity
- canonical evidence JSON and/or hash
- evidence version
- timestamp.

Required invariants:

- unique `(attempt_id, slot_ordinal)`;
- identities distinct across the pair;
- no historical campaign-slot identity reuse;
- no item mutation after `PAIR_READY`;
- no scoring, ranking, confidence, probability, weights or financial fields.

The exact-two-row invariant is enforced by the transaction owner plus focused schema tests; do not invent unsafe cross-table CHECK logic.

Do not require an eligible-reserve FK. The existing supply owner may lawfully surface retained protocol-confirmed candidates without first writing them to the reserve.

## 5. Source lineage

Add `printer_pre_admission_discovery_attempt_source_links` linking the attempt to existing governed source evidence:

- `attempt_id`
- `source_request_id`
- optional response id
- optional failure id
- logical stage identity.

Preserve existing provenance rules: response/failure requires request, response/failure are mutually exclusive for one fact, and source request identities are never synthesized or inferred from names.

This junction attributes existing Source-Governor facts; it does not replace source ledgers.

## 6. Scheduler contract addition

Add a new `JobKind`:

`PRE_ADMISSION_DISCOVERY_SELECTION`

Do not overload `DISCOVERY_REFRESH`.

Priority law:

- it must remain below all protected tracking/window-close/safety work;
- `DISCOVERY_REFRESH` also remains ahead of it;
- place `PRE_ADMISSION_DISCOVERY_SELECTION` immediately after `DISCOVERY_REFRESH` and before context/background jobs in `JOB_PRIORITY_ORDER`.

This reinforces, but does not replace, the factory disposition law that already-due lifecycle work outranks admission.

The attempt may begin source work only after this exact Scheduler job is due and successfully claimed by the canonical Scheduler owner.

Campaign active-work, safe-stop and cleanup projections must count active pre-admission attempts/Scheduler jobs so interruption cannot orphan invisible work.

No second Scheduler is introduced.

## 7. Reuse existing operational discovery owners

The new attempt is a persistence/ownership boundary, not a new discovery engine.

Reuse existing owners in order:

1. eligible-token supply / permanent-availability acquisition;
2. tracking-state eligibility/requalification;
3. existing holder/safety owner;
4. existing fixed eligibility gates;
5. existing deterministic uniform selection;
6. frozen exact pair persistence.

Eligible Token Supply alone is not final authority because permanent-availability output can still contain `HOLDER_SAFETY_DUE`.

Where holder/fixed-gate/uniform-selection behavior is trapped inside `CombinedPumpfunCampaignExecutor`, factor the minimum existing logic into reusable owner-local primitives and make both the existing cycle-rooted path and the pre-admission path call those same primitives.

Do not copy predicates or create a second policy.
Do not introduce scoring/ranking/confidence/weights.

## 8. One-shot execution law

```text
atomic attempt + Scheduler creation
-> Scheduler due/claim
-> PLANNED -> RUNNING
-> existing governed discovery/gates/selection
-> persist exact source lineage
-> terminalize once:
   PAIR_READY | NO_PAIR | BLOCKED | FAILED | CANCELLED
```

Once execution starts, no second attempt may be created for the same campaign/run/factory/proposed ordinal.

No automatic retry, restart, successor, polling loop, second runner or in-memory-only attempt authority.

Provider/supervision/budget failure keeps its existing classification; it must not be relabelled as market shortage.

## 9. Atomic Step-4 consumption

`PAIR_READY` does not create cycle 2.

Step 4 must consume it inside the existing admission transaction:

1. fresh `BEGIN IMMEDIATE`;
2. reload authoritative health/session state;
3. require exact matching, unconsumed `PAIR_READY` attempt;
4. load exactly two frozen items;
5. revalidate current admission gates and historical identity non-reuse;
6. create cycle 2 through existing `admit_two_token_cycle` / `create_cycle_with_two_slots` authority;
7. transition `PAIR_READY -> CONSUMED` and bind `consumed_cycle_id` in the same transaction;
8. commit.

If state changed, rollback and leave the attempt unconsumed. Never rerun discovery.

Prefer a narrow `admit_two_token_cycle_from_attempt(...)` composition instead of post-commit mutation.

## 10. Frozen-evidence materialization after admission

The attempt ledger does not replace normal cycle-rooted discovery/handoff ownership.

After successful cycle admission, materialize the frozen pair into the normal cycle-owned discovery/selection/handoff structures without:

- source refetch;
- reselection;
- changing either target;
- fabricating provenance.

Materialization must verify identity/evidence equivalence and reuse already-governed source evidence linked to the attempt.

Only after this materialization is proven may the factory schedule cycle-2 lifecycle steps.

## 11. TDD implementation order

A. migration/schema ownership RED/GREEN.

B. pure attempt persistence and state-machine RED/GREEN.

C. Scheduler job-kind + atomic attempt/job ownership + active-work/cleanup RED/GREEN.

D. factor existing holder/fixed-gate/uniform-selection owners with parity RED/GREEN.

E. one-shot later-cycle callback RED/GREEN.

F. atomic `PAIR_READY` consumption / cycle-2 admission RED/GREEN.

G. frozen-evidence cycle-rooted materialization/no-refetch RED/GREEN.

Only A-G PASS may resume Step 5 factory-loop integration.

## 12. Minimum proof / closeout

Use risk-based verification:

- migration 055 focused tests and fresh-schema migration-chain proof;
- FK/integrity checks;
- one-shot attempt and state-transition tests;
- Scheduler priority/claim/active-work tests;
- combined-discovery parity tests affected by factoring;
- holder/fixed-gate/uniform-selection parity;
- one-shot callback;
- exact atomic cycle-2 consumption;
- no-refetch materialization;
- public two-token path unchanged;
- `py_compile` touched modules;
- `git diff --check`.

Do not run broad suites after every seam. Reserve broader integrated verification for prerequisite closeout / Step-5 integration review.

No operational migration application, live source execution, proof authorization or four-token run is part of this implementation proof.

## 13. Money usefulness contribution

This seam lets Printer discover the second C/D pair exactly once and preserve its evidence across interruption without corrupting the already-running A/B lifecycle.

It improves durable ownership, source/Scheduler provenance, exact-pair continuity, atomic cycle admission, and operator explainability.

It still unlocks nothing financial or long-window: no proof runtime, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

1. Gate factoring must preserve exact existing behavior and avoid a parallel eligibility policy.
2. Frozen-evidence materialization must satisfy cycle-rooted schemas without refetch/reselection.
3. A RUNNING attempt must remain visible to safe-stop/cleanup after interruption.
4. Migration 055 implementation passing tests does not authorize applying it to the operational DB.
5. The new Scheduler job kind must remain lower priority than protected lifecycle/close work; future priority edits require parity tests.

## 15. Completion condition

The prerequisite closes only when:

- pre-admission attempt ownership is durable before cycle 2 exists;
- one canonical Scheduler job owns exactly one attempt;
- exact pair and source lineage are frozen and attributable;
- holder/fixed-gate/uniform-selection parity is proven;
- Step 4 consumes the attempt atomically without rediscovery;
- cycle-rooted materialization performs zero discovery refetch/reselection;
- existing public two-token behavior remains unchanged;
- prerequisite closeout passes.

Then V2-9.8B may resume the remaining factory-loop integration implementation.

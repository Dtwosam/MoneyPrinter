# Printer V1 V2-9.8B — Durable Pre-Admission Discovery Attempt Ownership Design

## Verdict

`V2_9_8B_PRE_ADMISSION_DISCOVERY_ATTEMPT_OWNERSHIP_DESIGN_PASS_READY_FOR_TDD_IMPLEMENTATION`

This design resolves the Step-3 blocker found after the admission-disposition/rearm implementation. It adds the minimum durable ownership seam required to execute exactly one later-cycle discovery/selection attempt before cycle 2 exists, while preserving the existing cycle-rooted discovery and lifecycle ownership contracts.

It does **not** authorize or run discovery, create cycle 2, integrate the factory loop, run the four-token proof, create authorization, activate 12h/24h, retrieval, decisions, positions, trades, audits, or PnL.

## 1. Authority and blocker

Use the active Printer V1 source stack together with:

- `docs/printer-v1-v2-9-8b-four-token-bounded-capacity-proof-integration-design.md`
- `docs/printer-v1-v2-9-8b-admission-health-and-wake-disposition-design.md`
- `docs/printer-v1-v2-9-8b-authoritative-admission-health-operator-review-closeout.md`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/multi_cycle_campaign_coordinator.py`
- `migrations/034_discovery_persistence_reconciliation.sql`
- `migrations/050_campaign_scheduler_ownership_scope.sql`
- `migrations/054_pre_lifecycle_discovery_refresh_wait.sql`

Current implementation HEAD before this design: `1e5e42623a925c84461ccbae0ca8df232f386786`.

The blocker is structural:

1. `CombinedPumpfunCampaignExecutor` requires the target campaign cycle to exist before discovery begins.
2. `printer_discovery_batches` is foreign-keyed to an existing campaign cycle.
3. the combined executor proceeds from selection directly into persisted handoff / first-15m scheduling instead of returning an unpersisted exact pair.
4. current `DISCOVERY_SELECTION` stage-scoped Scheduler ownership requires `factory_run_id IS NULL`, so it cannot represent a pre-admission attempt attributable to the exact authoritative factory run.
5. the pre-lifecycle discovery-refresh wait table is ownership evidence only and explicitly cannot substitute for discovery work.

No reusable durable pre-admission attempt/opportunity table exists.

## 2. Design decision — preserve cycle-rooted owners

Do **not** relax or rebuild migrations 034 or 050.

Do **not** create cycle 2 early merely to satisfy discovery foreign keys.

The existing cycle-rooted discovery batch, discovery work, campaign Scheduler-work, token-slot, window, and lifecycle tables remain unchanged. They continue to own work only after a cycle is lawfully admitted.

The repair is one additive, pre-admission ownership seam rooted in:

```text
campaign
  -> campaign run
  -> authoritative factory run
  -> proposed cycle ordinal / proposed cycle identity
  -> one pre-admission discovery attempt
  -> one Scheduler job
  -> zero or exactly two selected-item evidence rows
```

The proposed cycle identity is evidence only. No `printer_memory_factory_campaign_cycles` row exists until Step 4 later succeeds transactionally.

## 3. Additive schema owner

Add one forward-only migration, expected next migration number `055`, unless current repository state proves a different next number at implementation time.

### 3.1 `printer_pre_admission_discovery_attempts`

Required identity:

- `attempt_id` primary key
- `campaign_id`
- `campaign_run_id`
- `configuration_id`
- `authoritative_factory_run_id`
- `proposed_cycle_ordinal`
- `proposed_cycle_id`
- `scheduler_job_id` unique
- `cycle_cutoff`
- `evaluated_at`
- `selection_seed_identity`
- `attempt_state`
- `first_terminal_cause`
- `terminal_at`
- `consumed_cycle_id` nullable
- `consumed_at` nullable
- `created_at`
- `updated_at`

Foreign keys must bind campaign/run/configuration/factory/Scheduler identities that already exist. There is deliberately **no FK to a campaign cycle before consumption**.

Unique one-shot authority:

```text
UNIQUE(campaign_id, campaign_run_id, authoritative_factory_run_id,
       proposed_cycle_ordinal)
```

The four-token proof may therefore have only one durable pre-admission opportunity for cycle ordinal 2.

### 3.2 Attempt states

Allowed active states:

```text
PLANNED
RUNNING
```

Allowed terminal states:

```text
PAIR_READY
NO_PAIR
BLOCKED
FAILED
CANCELLED
CONSUMED
```

Terminal rows require `first_terminal_cause` and `terminal_at`.

`PAIR_READY` means exactly two immutable selected-item rows exist and the attempt may be presented to Step 4. It does not create lifecycle ownership.

`CONSUMED` is legal only after the exact pair has been atomically admitted as a real campaign cycle; `consumed_cycle_id` and `consumed_at` are then required.

No transition from a terminal no-pair/block/failure/cancel state back to active is allowed. No retry/restart/successor attempt is created.

## 4. Exact pair evidence

Add `printer_pre_admission_discovery_attempt_items`.

Exactly two rows are permitted for a `PAIR_READY` attempt:

- `attempt_id`
- `slot_ordinal` exactly 1 or 2
- `token_identity`
- `token_row_id`
- `mint_identity`
- `pair_identity`
- `pair_row_id`
- `lifecycle_identity`
- canonical market identity / pool identity as already used by the operational handoff owner
- selected evidence JSON or canonical evidence hash
- evidence version
- `created_at`

Required invariants:

- unique `(attempt_id, slot_ordinal)`;
- slot ordinals exactly `{1,2}` for `PAIR_READY`;
- token/mint/pair/lifecycle identities distinct across the pair;
- selected identities cannot reuse any historical campaign slot identity;
- evidence is immutable after `PAIR_READY`;
- no ranking, score, confidence, probability, weight, BUY/SELL/HOLD, position, trade, or PnL field.

Do not require an eligible-reserve FK. The existing supply owner can legitimately produce an observation-eligible retained protocol promotion without first persisting it to `printer_eligible_token_reserve`.

## 5. Source lineage

Add a narrow attempt-source junction, for example `printer_pre_admission_discovery_attempt_source_links`.

Each provider-reaching request used by the attempt is linked by existing source ledger IDs:

- `attempt_id`
- `source_request_id`
- optional `source_response_id`
- optional `source_failure_id`
- logical stage identity

Preserve existing source provenance law:

- response or failure requires request;
- response and failure are mutually exclusive for the same linked attempt fact;
- no synthetic request identity;
- no parsing request keys as ownership authority.

The junction does not replace the canonical source ledgers. It only attributes existing governed source evidence to the pre-admission attempt.

## 6. Scheduler ownership

The pre-admission attempt owns one canonical Central Scheduler job and the exact authoritative factory-run identity.

Do not create a second Scheduler.

Do not use the pre-lifecycle wait table as work ownership.

Do not silently reinterpret a refresh job as a new admission-selection job.

Implementation must first audit the Scheduler contract:

- if an existing semantically correct discovery job kind can own one bounded pre-admission selection attempt, reuse it;
- otherwise STOP before implementation of runtime behavior and design the smallest Scheduler-contract addition.

No source work may begin before the exact Scheduler job is due and successfully claimed by the canonical owner.

Campaign active-work / cleanup projections must include the new active attempt so terminal cleanup cannot ignore a RUNNING pre-admission discovery action.

## 7. Reuse existing discovery and gate owners

The new attempt is an ownership/persistence boundary, **not a new discovery engine**.

Reuse existing owners in this order:

1. canonical eligible-token supply / permanent-availability acquisition for graduated Solana memecoin candidates;
2. existing current tracking-state eligibility/requalification checks;
3. existing holder/safety evidence owner;
4. existing fixed eligibility gates;
5. existing deterministic uniform selection owner;
6. exact pair persistence into the attempt item rows.

Where holder/fixed-gate/uniform-selection logic is currently trapped inside `CombinedPumpfunCampaignExecutor`, factor the existing logic into reusable owner-local primitives and make both the existing cycle-rooted path and the pre-admission path call the same primitive.

Do not copy the predicates into a second implementation.

Do not introduce scoring/ranking/confidence/weights. Deterministic uniform selection remains the existing categorical selection law.

The existing Eligible Token Supply reserve alone is insufficient as final pair authority because permanent-availability results can still have `HOLDER_SAFETY_DUE`; those candidates must pass the existing holder/safety and downstream fixed gates before `PAIR_READY`.

## 8. One-shot execution law

For proposed cycle 2:

```text
create exact attempt row
-> enqueue one canonical Scheduler job
-> claim once when due
-> transition PLANNED -> RUNNING
-> execute the existing governed discovery/gate/selection owners
-> persist source lineage as work occurs
-> terminalize exactly once as:
     PAIR_READY | NO_PAIR | BLOCKED | FAILED | CANCELLED
```

Once the Scheduler-owned attempt begins, the proof controller must never invoke another discovery attempt for the same campaign/run/factory/proposed ordinal.

No automatic retry.
No restart.
No successor.
No independent polling loop.
No second runner.
No in-memory-only attempt authority.

Provider/capacity or supervision failure terminalizes honestly according to its existing owner; it does not become market shortage.

## 9. Step-4 consumption contract

`PAIR_READY` does not admit cycle 2 by itself.

Step 4 later consumes the attempt transactionally:

1. open the existing coordinator's fresh `BEGIN IMMEDIATE` admission transaction;
2. reload authoritative admission health/session state;
3. require the attempt still equals `PAIR_READY`, is unconsumed, and matches the exact campaign/run/configuration/factory/proposed ordinal;
4. reload exactly two immutable attempt items;
5. revalidate historical identity non-reuse and current admission gates;
6. use the existing `create_cycle_with_two_slots` / `admit_two_token_cycle` authority to create cycle 2;
7. bind the attempt to the new `cycle_id` and transition `PAIR_READY -> CONSUMED` **inside the same transaction**;
8. only after commit may normal cycle-rooted discovery/handoff/lifecycle owners materialize or schedule cycle-2 lifecycle work from the frozen pair.

If admission state changed, rollback and leave the attempt unconsumed. Do not rerun discovery.

A narrow composition such as `admit_two_token_cycle_from_attempt(...)` is preferred over post-commit attempt mutation because it preserves atomic consumption.

## 10. Materialization after consumption

The pre-admission ledger does not replace `printer_discovery_batches`, `printer_discovery_work`, selection links, campaign Scheduler-work, or first-15m handoff ownership.

After Step 4 successfully creates cycle 2, the existing cycle-rooted path may materialize the immutable selected-pair evidence into the normal cycle-owned discovery/handoff structures **without refetching, reselecting, or changing the pair**.

Materialization must verify byte-/identity-equivalence to the frozen attempt items and must use the already-governed source evidence linked to the attempt. It must not issue new discovery source calls merely to recreate lineage.

The implementation plan must decide the smallest factoring surface needed for this materialization and prove it with focused TDD before factory-loop integration.

## 11. Migration boundary

This design authorizes implementation of an additive schema migration only in code/tests. It does **not** authorize applying that migration to the authoritative operational database in this prerequisite implementation lane.

Minimum migration proof before any future operational application:

- fresh-schema migration chain applies cleanly;
- `PRAGMA foreign_key_check` clean;
- `PRAGMA integrity_check` clean;
- existing historical rows untouched;
- no rebuild of migrations 034/050 tables;
- one-attempt uniqueness enforced;
- terminal-state invariants enforced;
- exact-two-item `PAIR_READY` invariant enforced by schema plus transaction owner;
- existing public two-token path unchanged when pre-admission controller is absent.

Operational migration application remains a separate explicitly reviewed readiness step before any bounded runtime proof.

## 12. TDD implementation sequence

### A. Schema ownership RED/GREEN

Prove the new attempt/item/source-link ownership model, one-shot uniqueness, terminal-state invariants, exact factory/Scheduler attribution, and no cycle FK before consumption.

### B. Pure persistence owner RED/GREEN

Implement create/claim-transition/terminalize/load/consume primitives with strict compare-and-update semantics. No sources or Scheduler execution in this seam.

### C. Scheduler ownership RED/GREEN

Prove one canonical Scheduler job owns the attempt and active-work/cleanup sees it. If no semantically correct existing job kind exists, STOP for the tiny Scheduler-contract design before adding one.

### D. Existing discovery-owner factoring RED/GREEN

Factor only the minimum existing holder/fixed-gate/uniform-selection primitives needed by both cycle-rooted and pre-admission execution. Prove parity with the existing combined executor.

### E. One-shot callback RED/GREEN

Bind the existing later-cycle callback to the pre-admission attempt owner. Exactly one attempt can start. Result is exact pair or honest terminal no-pair/block/failure/cancel.

### F. Step-4 atomic consumption RED/GREEN

Add the narrow coordinator composition that consumes a frozen `PAIR_READY` attempt and creates cycle 2 atomically.

### G. Frozen-evidence materialization RED/GREEN

Materialize cycle-rooted discovery/handoff evidence from the consumed attempt without source refetch or reselection.

Only after A-G PASS may the existing Step-5 factory-loop integration resume.

## 13. Proof and closeout requirements

Minimum sufficient verification for the prerequisite implementation:

- migration tests for new schema only;
- focused attempt ownership/persistence tests;
- Scheduler ownership/active-work tests;
- existing combined discovery parity tests affected by factoring;
- exact holder/fixed-gate/uniform-selection parity tests;
- one-shot callback tests;
- exact atomic cycle-2 consumption tests;
- frozen materialization/no-refetch tests;
- `py_compile` touched modules;
- `git diff --check`.

Do not run a broad regression suite after every sub-step. Reserve broader integration verification for the prerequisite closeout / resumed Step-5 integration checkpoint.

No live source execution, no operational DB mutation, no proof authorization, and no real four-token run are part of this implementation proof.

## 14. Money usefulness contribution

This seam makes the second pair C/D discoverable without risking duplicate attempts, ambiguous ownership, or corruption of the already-running A/B lifecycle. It lets Printer spend one bounded later-cycle discovery opportunity and carry its evidence safely into the same authoritative factory run.

It improves:

- durable one-shot ownership;
- exact Source Governor/Scheduler provenance;
- deterministic selected-pair continuity;
- atomic cycle-2 admission safety;
- operator explainability after interruption.

It still does **not** unlock:

- the four-token runtime proof;
- 12h/24h runtime;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trades, audits, or PnL.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

1. **Scheduler semantics:** the current public Scheduler contract exposes `DISCOVERY_REFRESH`, but that name may not be semantically exact for pre-admission selection. Do not reuse it blindly; stop for a tiny contract design if necessary.
2. **Gate factoring:** holder/fixed-gate/selection logic currently lives partly inside the combined executor. Factoring must preserve exact behavior and avoid a parallel policy path.
3. **Evidence materialization:** the cycle-rooted schema still expects normal discovery/handoff evidence after admission. Materialization must consume frozen evidence without refetching or reselection.
4. **Operational migration:** the new migration cannot be applied to the authoritative DB merely because implementation tests pass; operational application requires a separate readiness review.
5. **Interruption safety:** a RUNNING attempt must remain durably attributable after process interruption and must terminalize/recover through existing supervision laws without creating another attempt.

## 16. Completion condition

This prerequisite is complete only when:

- durable pre-admission attempt ownership exists;
- one Scheduler-owned attempt is representable before cycle 2 exists;
- exact pair evidence is immutable and source-attributable;
- holder/fixed-gate/uniform-selection parity is proven;
- Step 4 can consume the pair atomically without rerunning discovery;
- cycle-rooted materialization requires zero discovery refetch/reselection;
- existing public two-token behavior remains unchanged;
- focused prerequisite closeout passes.

Then V2-9.8B may resume the remaining factory-loop integration implementation.

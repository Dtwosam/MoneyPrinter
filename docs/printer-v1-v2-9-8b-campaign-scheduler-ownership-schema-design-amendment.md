# Printer V1 V2-9.8B Campaign Scheduler Ownership Schema Design Amendment

Date: 2026-08-01

Lane:
`V2-9.8B Campaign Scheduler Ownership Schema Design Amendment`

Type: design/specification only.

Audited implementation baseline:
`71717a6d619e41a2f8a8aa0b5421930f73a7c59d`

Implementation evidence reviewed:
`ec8a5b57789116a8969800b910d29b18daa98bb2`

Verdict:
`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_DESIGN_AMENDMENT_PASS`

## 0. Boundary

This amendment designs the minimum schema repair required by the blocked
full-run accounting implementation. It does not add a migration, change runtime
code, run tests, contact sources, mutate any database, authorize a campaign, or
unlock a later capability.

Use it with the active Printer V1 source stack, the approved full-run accounting
design, and `docs/printer-v1-v2-9-8b-full-run-accounting-final-conformance-map.md`.

Required sequence:

```text
audited blocker -> design amendment -> migration implementation -> disposable proof -> closeout -> resume C1-C15 implementation
```

## 1. Confirmed schema blocker

`printer_memory_factory_campaign_scheduler_work` currently requires both
`token_slot_id` and `window_id` and binds them through a composite foreign key to
`printer_memory_factory_campaign_windows`.

That is correct for window lifecycle jobs but cannot represent all campaign
Scheduler families required by the approved design:

- discovery and selection jobs exist before a campaign window;
- first-15m handoff jobs may be linked by a selected-item row before a window;
- terminal cleanup may cancel any exact campaign-scoped job and is not itself a
  window lifecycle step.

Migration `047_campaign_oneshot_linkage_binds.sql` correctly makes scheduler-work
identity columns immutable, so a fake window row cannot be inserted and repaired
later.

The current `project_campaign_scheduler_job()` helper is also lifecycle-only. It
requires a factory run, token slot, window, and a matching
`printer_memory_factory_run_steps` row. Legitimate discovery, handoff, and cleanup
jobs therefore fail closed.

This cannot be repaired honestly by:

- sentinel windows or slots;
- late back-filling of immutable identity;
- excluding non-window jobs from full equality;
- adding a second operational Scheduler-ownership authority;
- using post-hoc counts as ownership.

## 2. Design decision

Generalize the existing
`printer_memory_factory_campaign_scheduler_work` table through one forward-only
migration.

It remains the single campaign Scheduler ownership authority. Do not add a
parallel operational ownership table.

Historical rows remain readable and immutable. New repaired rows use a
stage-scoped ownership contract capable of representing both window-bound and
non-window campaign work.

## 3. Required ownership scopes

```text
DISCOVERY_SELECTION
FIRST_15M_HANDOFF
WINDOW_LIFECYCLE
TERMINAL_CLEANUP
```

Every attributable Scheduler job has exactly one campaign ownership row and one
accounting stage.

Required common identity:

```text
scheduler_work_id
campaign_id
run_id
cycle_id
stage_id
work_scope
work_intent
scheduler_job_id
target_category
target_identity
work_state
first_terminal_cause
terminal_at
```

Optional scope-specific identity:

```text
factory_run_id
token_slot_id
window_id
source_request_id
source_response_id
source_failure_id
```

## 4. Compatibility contract

Add an immutable ownership-contract version:

```text
V1_WINDOW_BOUND
V2_STAGE_SCOPED
```

Existing rows migrate as `V1_WINDOW_BOUND`. New repaired operational rows must
use `V2_STAGE_SCOPED`.

Historical V1 rows are not upgraded into repaired V2 proof merely because the
schema was migrated.

## 5. Target schema rules

The rebuilt table adds:

```text
ownership_contract_version TEXT NOT NULL
stage_id TEXT
work_scope TEXT
target_category TEXT
target_identity TEXT
factory_run_id TEXT
```

For V2 rows, `stage_id`, `work_scope`, `target_category`, `target_identity`, and
`scheduler_job_id` are mandatory.

### WINDOW_LIFECYCLE

Requires:

- non-null `factory_run_id`;
- non-null `token_slot_id`;
- non-null `window_id`;
- the exact composite window/slot foreign key;
- exact factory run-step linkage.

### FIRST_15M_HANDOFF

Requires:

- an exact selected-item or token-slot ownership source;
- no fabricated window;
- `window_id IS NULL`;
- no later mutation into another scope.

### DISCOVERY_SELECTION

Requires:

- an exact discovery or selection ownership source;
- no fabricated slot or window;
- deterministic stage and target identity.

### TERMINAL_CLEANUP

Requires:

- the exact Scheduler job to belong to the captured campaign-scoped job set
  before cancellation;
- real pre-cancellation and terminal state evidence;
- no fabricated window or factory run-step link.

`token_slot_id` and `window_id` become nullable only under these conditional
scope laws. Explicit CHECK constraints must reject partial or invalid
combinations.

## 6. Uniqueness invariant

Add a unique partial index:

```text
UNIQUE(scheduler_job_id) WHERE scheduler_job_id IS NOT NULL
```

This enforces one canonical Scheduler job to one campaign ownership stage.

Before migration, a read-only readiness audit must prove no existing row violates
this invariant. Any conflict blocks migration and requires a separate historical
disposition design. It must not be auto-repaired.

## 7. Migration strategy

Derive the next canonical migration number from the live migrations directory.
If `049` remains latest, the expected filename is:

`050_campaign_scheduler_ownership_scope.sql`

Do not hard-code that number without checking the repository.

SQLite requires a table rebuild.

Required sequence:

1. `BEGIN IMMEDIATE`;
2. execute pre-copy invariant queries;
3. create the replacement table;
4. copy historical rows as `V1_WINDOW_BOUND` without changing any existing
   identity, linkage, status, terminal cause, or timestamp;
5. verify row-count and canonical-field equality;
6. drop the old table and rename the replacement;
7. recreate indexes, foreign keys, and state checks;
8. replace the immutability trigger with the amended identity contract;
9. add the unique Scheduler-job partial index;
10. run foreign-key and integrity checks;
11. commit only if all checks pass.

Migration idempotency comes from the canonical migration ledger, not from
silently tolerating a partial rebuild.

Do not apply this migration to the authoritative database in the implementation
or disposable-proof lanes.

## 8. One scope-aware projection owner

Generalize the existing helper into one authority, for example:

`project_campaign_scheduler_work()`

Ownership validation by scope:

| Scope | Durable ownership source |
| --- | --- |
| `DISCOVERY_SELECTION` | discovery work, selection batch/item, or canonical discovery link |
| `FIRST_15M_HANDOFF` | selected-item link carrying `first_window_15m_scheduler_job_id` |
| `WINDOW_LIFECYCLE` | exact factory run-step and campaign window/slot |
| `TERMINAL_CLEANUP` | exact campaign-scoped job set captured before cancellation |

The helper must:

- reference the existing Central Scheduler job;
- create no replacement job;
- reject competing campaign, scope, stage, or target ownership;
- be idempotent only for the exact same identity;
- preserve actual terminal state;
- never fabricate a window or run-step link.

`project_campaign_scheduler_job()` may remain only as a compatibility wrapper for
`WINDOW_LIFECYCLE`; it must delegate to the single scope-aware owner.

## 9. Accounting, report, and replay

The resumed full-run implementation must:

- observe Scheduler enqueue, claim, terminal, and cleanup boundaries directly;
- project every attributable job through this one owner;
- place every job in one deterministic stage;
- compare full owner and action-local Scheduler identity sets bidirectionally;
- block on missing, extra, duplicate, active, locked, or conflicting work.

The canonical report must expose each ownership row's job, stage, scope, target,
optional factory/window/slot linkage, real state, and first cause.

Scheduler attribution must derive from exact scope values, not string heuristics.

Public exact-identity report-only must reconstruct the same ownership set and
canonical hashes with zero source, Scheduler, and write activity.

## 10. Focused implementation proof

Use temporary databases only.

Positive proofs:

1. historical schema migrates with no row or identity loss;
2. V1 rows remain readable and immutable;
3. discovery work can be owned without a window or slot;
4. handoff work can be owned without a window;
5. lifecycle work requires exact window/slot/factory linkage;
6. cleanup cancellation can be owned without a window;
7. all four scopes coexist in one table and helper;
8. one Scheduler job cannot appear across multiple scopes or stages;
9. exact-repeat projection is idempotent;
10. exact report-only reconstruction performs zero writes.

Negative proofs:

1. duplicate job ownership blocks;
2. non-window scope with a window blocks;
3. lifecycle scope without exact linkage blocks;
4. fake or unrelated ownership source blocks;
5. scope or target mutation blocks;
6. partial rebuild rolls back;
7. V1 rows cannot satisfy V2 proof;
8. migration readiness blocks on existing duplicate job ownership.

## 11. Resume conditions

C1-C15 implementation remains frozen until:

1. this amendment is operator-reviewed and integrated;
2. migration implementation passes focused disposable tests;
3. bounded disposable migration proof passes;
4. migration closeout is integrated;
5. the full-run implementation is rebuilt or rebased from the accepted schema
   baseline rather than merging prior false-PASS claims directly.

## 12. Money-usefulness contribution

This amendment ensures discovery, handoff, lifecycle, and cleanup costs remain
fully attributable before future memory can influence paper-only decisions.

It prevents work from disappearing merely because no window existed yet and
prevents one Scheduler job from being counted in multiple stages.

It makes no profit claim and unlocks no trading capability.

## 13. What remains locked

This amendment does not unlock:

- authoritative database migration;
- the remaining C1-C15 implementation;
- bounded or live campaigns;
- `WINDOW_1H` or later windows;
- retrieval;
- paper decisions;
- BUY, SELL, or HOLD;
- positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Mitigation | Required proof |
| --- | --- | --- |
| SQLite rebuild loses historical truth | Exact pre/post row and field equality | Disposable migration copy and rollback tests |
| Existing duplicate job ownership | Read-only readiness block | Duplicate-invariant query and negative fixture |
| Nullable window/slot weakens lifecycle rows | Scope-conditional checks and foreign keys | Invalid-combination tests |
| Cleanup captured after cancellation | Capture campaign job set and pre-state first | Boundary-order integration test |
| Compatibility wrapper becomes a second owner | Wrapper delegates only | Caller and duplicate tests |
| Historical V1 evidence is upgraded | Contract-version gate | Historical replay negative test |
| Migration mixed with broad runtime repair | Isolate implementation, proof, and closeout | Focused diff review |
| Authoritative DB migrated early | Explicit later readiness and authorization | DB hash/readiness gate |

## 14. Verdict and next lane

Verdict:

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_DESIGN_AMENDMENT_PASS`

Exact next permitted lane after operator review and integration:

`V2-9.8B Campaign Scheduler Ownership Schema Migration Implementation`

That lane may add only the approved forward migration, scope-aware projection
owner, compatibility wrapper changes, focused disposable tests, and an
implementation report. It may not resume C1-C15 runtime repair or run an
operational campaign.
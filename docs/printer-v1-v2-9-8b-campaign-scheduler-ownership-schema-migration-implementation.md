# Printer V1 V2-9.8B Campaign Scheduler Ownership Schema Migration Implementation

Date: 2026-08-01

Lane:
`V2-9.8B Campaign Scheduler Ownership Schema Migration Implementation`

Baseline `master` HEAD:
`251ff21f8dddfe3eeab7d2d2d2cb275660578ce1`

Implementation branch:
`codex/v2-9-8b-scheduler-ownership-schema-migration`

Controlling design amendment:
`docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-design-amendment.md`
(`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_DESIGN_AMENDMENT_PASS`)

Current verdict (correction "scheduler ownership projection truth"):
`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_IMPLEMENTATION_PASS`

> **Superseded prior result.** The original PASS recorded in §1–§12 below was
> issued before the projection authority proved *exact Scheduler state* and
> *exact job lineage* for all four scopes. That earlier PASS is preserved
> unchanged as the historical record. §13 documents the correction that now
> controls the current verdict. See §13 for the exact corrections, revised
> tests, and the unchanged schema decision.

## 0. Boundary

This lane adds only the approved forward migration, the single scope-aware
projection owner, its `WINDOW_LIFECYCLE` compatibility wrapper, focused
disposable tests, and this report. It does not apply the migration to the
authoritative database, wire the owner into the operational campaign, run any
operational/provider/RPC/WebSocket path, or unlock retrieval, decisions,
BUY/SELL/HOLD, positions, trades, audits, or PnL. It does not merge the branch.

## 1. Exact migration filename

Derived from the live ordered `migrations/*.sql` directory (`049` was latest):

`migrations/050_campaign_scheduler_ownership_scope.sql`

## 2. Files changed

| File | Change |
| --- | --- |
| `migrations/050_campaign_scheduler_ownership_scope.sql` | New forward-only rebuild of `printer_memory_factory_campaign_scheduler_work`. |
| `src/printer_v1/operator_cli/campaign_ownership.py` | Added `project_campaign_scheduler_work()` (single authority), `project_campaign_scheduler_job()` wrapper, `SchedulerWorkProjectionResult`, per-scope validators; tagged legacy `persist_scheduler_work()` inserts `V1_WINDOW_BOUND`. |
| `tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py` | New focused disposable tests (21 cases). |
| `docs/printer-v1-v2-9-8b-campaign-scheduler-ownership-schema-migration-implementation.md` | This report. |

## 3. Schema before/after

### Before (migration 032, immutability amended by 047)

```text
printer_memory_factory_campaign_scheduler_work(
    scheduler_work_id TEXT PK,
    campaign_id, run_id, cycle_id            NOT NULL,
    token_slot_id                            NOT NULL,   -- window-only
    window_id                                NOT NULL,   -- window-only
    work_intent, deadline_at                 NOT NULL,
    work_state                               NOT NULL CHECK(...),
    scheduler_job_id, source_request_id, source_response_id, source_failure_id,
    first_terminal_cause, terminal_at,
    created_at, updated_at                    NOT NULL,
    UNIQUE(scheduler_work_id, window_id, token_slot_id, cycle_id, run_id, campaign_id),
    FK (window_id, token_slot_id, cycle_id, run_id, campaign_id) -> campaign_windows,
    FK scheduler_job_id -> printer_scheduler_jobs,
    FK source_* -> source tables,
    source-provenance CHECKs, work-state/terminal CHECK
)
```

Only window lifecycle jobs could be represented; discovery, selection,
first-15m handoff, and terminal cleanup jobs failed closed because
`token_slot_id`/`window_id` were mandatory and composite-FK bound.

### After (migration 050)

Added columns:

```text
ownership_contract_version TEXT NOT NULL CHECK (IN ('V1_WINDOW_BOUND','V2_STAGE_SCOPED'))
stage_id                   TEXT
work_scope                 TEXT CHECK (NULL OR IN ('DISCOVERY_SELECTION','FIRST_15M_HANDOFF','WINDOW_LIFECYCLE','TERMINAL_CLEANUP'))
target_category            TEXT
target_identity            TEXT
factory_run_id             TEXT   (FK -> printer_memory_factory_runs(run_id))
```

`token_slot_id` and `window_id` become nullable **only** under the conditional
scope laws below. All prior columns, the composite `UNIQUE`, every foreign key,
the source-provenance CHECKs, and the work-state/terminal CHECK are preserved.

New invariant:

```text
UNIQUE(scheduler_job_id) WHERE scheduler_job_id IS NOT NULL
  -> idx_campaign_work_scheduler_job_unique
```

Indexes: `idx_campaign_work_owner` (recreated), `idx_campaign_work_scheduler_job_unique`
(new partial unique), `idx_campaign_work_scope_stage` (new reporting index).

Triggers recreated on the rebuilt table:
`printer_campaign_work_provenance_insert` (unchanged) and the amended
`printer_campaign_work_identity_immutable` (now also makes
`ownership_contract_version`, `stage_id`, `work_scope`, `target_category`,
`target_identity`, `factory_run_id` immutable, while keeping the 047
"immutable once bound" semantics for `scheduler_job_id` and source ids).

## 4. Scope validation matrix

Schema-level CHECK constraints (fail-closed nullability):

| Contract / scope | window_id | token_slot_id | factory_run_id | Other mandatory |
| --- | --- | --- | --- | --- |
| `V1_WINDOW_BOUND` | NOT NULL | NOT NULL | NULL | scope/stage/target all NULL |
| `V2` `DISCOVERY_SELECTION` | NULL | NULL | NULL | stage/scope/target/job |
| `V2` `FIRST_15M_HANDOFF` | NULL | (optional) | NULL | stage/scope/target/job |
| `V2` `WINDOW_LIFECYCLE` | NOT NULL | NOT NULL | NOT NULL | stage/scope/target/job |
| `V2` `TERMINAL_CLEANUP` | NULL | (optional) | NULL | stage/scope/target/job |

Every `V2_STAGE_SCOPED` row also requires non-empty `stage_id`,
`work_scope`, `target_category`, `target_identity`, and non-null
`scheduler_job_id`. Partial or contradictory combinations fail the CHECK
constraints (fail closed).

Helper-level durable ownership validation (`project_campaign_scheduler_work`):

| Scope | Durable ownership source verified |
| --- | --- |
| `DISCOVERY_SELECTION` | `printer_discovery_batches` (`DISCOVERY_BATCH`) or `printer_discovery_selection_links` (`SELECTION_BATCH`), scoped to campaign/run/cycle |
| `FIRST_15M_HANDOFF` | `printer_discovery_selected_item_links.first_window_15m_scheduler_job_id` == the projected job, scoped to campaign/run/cycle; token slot + target identity must match the link |
| `WINDOW_LIFECYCLE` | exact `printer_memory_factory_campaign_windows` (window/slot/cycle/run/campaign) **and** exact `printer_memory_factory_run_steps` (factory run + scheduler job) |
| `TERMINAL_CLEANUP` | job present in the caller's captured campaign-scoped set, and every captured job provably campaign-scoped via an existing ownership row, run-step, or handoff link |

Always: the projected `scheduler_job_id` must reference an existing
`printer_scheduler_jobs` row; the helper never creates a Scheduler job.

## 5. Historical preservation proof

The migration:

1. runs a read-only duplicate-readiness guard on the live table before any copy;
2. copies every historical row into the rebuilt table with
   `ownership_contract_version='V1_WINDOW_BOUND'` and all new V2 columns NULL,
   changing no existing identity, linkage, status, terminal cause, or timestamp;
3. proves exact row-count equality;
4. proves exact field equality on all 17 preserved columns in both directions
   via compound `EXCEPT` (NULLs compared equal);
5. only then drops/renames, recreates indexes/triggers, and runs
   `pragma_foreign_key_check` and `pragma_integrity_check` guards.

Test `test_01_historical_rows_migrate_without_drift` seeds a real FK-valid
window chain plus two historical rows (one live/`PENDING` with a bound job, one
terminal/`SUCCEEDED` with a null job and terminal cause) and asserts the full
17-column snapshot is byte-identical before and after, with every row tagged
`V1_WINDOW_BOUND`.

## 6. Helper changes

- `project_campaign_scheduler_work(...)` — the single scope-aware Scheduler
  ownership authority. References an existing Central Scheduler job; creates
  none; validates each scope against its real durable source; is idempotent only
  for the exact same complete identity (returns `created=False`); rejects
  competing campaign/scope/stage/target/linkage ownership and duplicate job
  ownership; preserves actual work state and first terminal cause on idempotent
  re-projection; never fabricates a window, slot, or run-step.
- `project_campaign_scheduler_job(...)` — compatibility wrapper for
  `WINDOW_LIFECYCLE` only; delegates to the single owner; introduces no second
  ownership authority.
- `persist_scheduler_work(...)` — legacy window-bound inserter; now tags its
  rows `V1_WINDOW_BOUND` so it keeps working post-migration without becoming a
  V2 ownership path.
- No second ownership table or helper authority was introduced.

## 7. Tests and outputs

New file: `tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py`
(21 cases, disposable temp databases only).

```text
$ .venv/bin/python -m pytest tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py -q
.....................                                                    [100%]
21 passed in 6.28s
```

Coverage against the required proofs:

| # | Requirement | Test(s) |
| --- | --- | --- |
| 1 | Historical rows migrate without drift | `test_01_historical_rows_migrate_without_drift` |
| 2 | FK + integrity checks pass; partial unique index present | `test_02_foreign_key_and_integrity_pass` |
| 3 | V1 rows readable and immutable | `test_03_v1_rows_readable_and_immutable` |
| 4 | Discovery/selection without slot/window | `test_04_...`, `test_04b_...` |
| 5 | Handoff without a window | `test_05_...`, `test_05b_...` |
| 6 | Lifecycle requires exact factory/window/slot/run-step | `test_06_...`, `test_06b_...`, `test_06c_...` |
| 7 | Cleanup without a window using a captured job | `test_07_...`, `test_07b_...` |
| 8 | All four scopes coexist | `test_08_all_four_scopes_coexist` |
| 9 | Duplicate Scheduler job ownership blocks | `test_09_duplicate_scheduler_job_blocks` |
| 10 | Exact-repeat projection idempotent | `test_10_exact_repeat_idempotent` |
| 11 | Competing scope/stage/target/campaign/linkage blocks | `test_11_competing_identity_blocks` |
| 12 | Invalid nullable-field combinations block | `test_12_invalid_nullable_combinations_block` |
| 13 | Identity mutation blocks | `test_13_identity_mutation_blocks` |
| 14 | Duplicate historical ownership blocks migration readiness | `test_14_duplicate_historical_job_blocks_migration` |
| 15 | Injected mid-rebuild failure rolls back | `test_15_injected_failure_rolls_back` |
| 16 | V1 rows cannot be treated as V2 evidence | `test_16_v1_rows_cannot_be_v2_evidence` |

Consolidated directly-affected migration/ownership/schema run:

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py \
    tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py \
    tests/test_v2_9_7d_6b_5_operational_lease_safe_stop.py \
    tests/test_v2_9_7d_6b_6_final_campaign_report.py \
    tests/test_v2_9_7e_42_direct_migration_discovery.py \
    tests/test_v2_9_1_proof_db_schema_readiness.py \
    tests/test_v2_9_7d_6b_2_operational_backup_restore_preflight.py -q
82 passed, 10 subtests passed in 15.54s
```

No full repository regression suite was run.

## 8. Pre-existing, out-of-scope stale tests

Two hard-coded snapshot tests assert a frozen "latest migration" that predates
this lane and already fail on clean `master` (`251ff21`), independent of this
change:

- `tests/test_phase1_database_schema.py::...::test_migration_runner_is_idempotent`
  expects the migration list to end at `034`.
- `tests/test_v2_9_7d_6b_8_isolated_slice_6_integration.py::...::test_completed_slice_6_components_work_together`
  expects `latest_rehearsed_migration == 035_...`.

Both were verified failing on the clean baseline before any change in this lane
(observed latest `049`); adding migration `050` only shifts the observed latest.
They are stale fixtures unrelated to Scheduler ownership and are intentionally
left untouched, per the lane's "run only directly affected tests / no broad
regression fixes" boundary.

## 9. Schema risks

| Risk | Mitigation |
| --- | --- |
| SQLite rebuild loses historical truth | Row-count + full field-equality guards; disposable copy test proves zero drift. |
| Dropping a table referenced by `campaign_objects` FK | Rebuild runs with `PRAGMA foreign_keys=OFF`; the composite `UNIQUE` is preserved so the objects FK re-resolves after rename; `pragma_foreign_key_check` guard re-verifies before commit. |
| Nullable window/slot weakens lifecycle rows | Scope-conditional CHECK constraints + composite window FK + helper run-step validation. |
| Existing duplicate job ownership | Read-only duplicate-readiness guard blocks migration; not auto-repaired. |
| Historical V1 evidence upgraded to V2 | Contract-version gate; helper rejects reuse of V1 rows/ids as V2; V1 row still occupies the unique job slot. |
| Partial rebuild on failure | All work inside `BEGIN IMMEDIATE`; guard CHECK failures abort before `COMMIT`; injected-failure test proves full rollback with no partial schema or row loss. |

## 10. What remains locked

Unchanged from the amendment: authoritative database migration, C1-C15
implementation, bounded or live campaigns, `WINDOW_1H`+ windows, retrieval,
paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets/keys/
signing/real funds/live execution, paid APIs, and any scoring/ranking/weighting/
embeddings. The scope-aware owner is not wired into the operational campaign.

## 11. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status | Notes |
| --- | --- | --- |
| Functionality risk: `project_campaign_scheduler_job` referenced in the C7 conformance map did not yet exist on `master` | Resolved | Implemented fresh as a thin `WINDOW_LIFECYCLE` wrapper over the single owner; no second authority. |
| Setback: two pre-existing stale snapshot tests fail on any new migration | Documented | Verified failing on clean `master`; out of lane scope. |
| Efficiency blocker: none | — | Migration is O(rows) single-pass copy with set-based guards; no runtime path touched. |

## 12. Implementation verdict

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_IMPLEMENTATION_PASS`

A PASS does not authorize applying the migration to the authoritative database
or resuming C1-C15. Next permitted lane after operator review/integration is the
bounded disposable migration proof.

> The §12 verdict above is the **historical** result of the first implementation
> pass. It is retained verbatim and is **superseded** by §13.

## 13. Correction — scheduler ownership projection truth

Date: 2026-08-01. Correction commit: `Correct scheduler ownership projection
truth`.

The first pass built the table, wrapper, and tests but the projection authority
accepted a caller-supplied Scheduler state and terminal cause, and proved
discovery/selection and cleanup ownership by *presence* rather than by *exact
Scheduler job lineage*. That is not honest ownership. This correction rewrites
the single scope-aware authority `project_campaign_scheduler_work()` (and its
`WINDOW_LIFECYCLE` wrapper) and its focused tests only. **No schema change was
required**: migration `050_campaign_scheduler_ownership_scope.sql` is unchanged;
all corrections use columns it already provides (`work_scope`, `stage_id`,
`target_category`, `target_identity`, `factory_run_id`).

### 13.1 Files changed

| File | Change |
| --- | --- |
| `src/printer_v1/operator_cli/campaign_ownership.py` | Corrected `project_campaign_scheduler_work()` to derive state from the canonical Scheduler; added `SchedulerCleanupCapture` + `capture_campaign_active_scheduler_jobs()`; added `_resolve_scheduler_state`, `_durable_scheduler_terminal_evidence`, `_scheduler_job_in_exact_scope`; rewrote all four scope validators; removed the untyped cleanup job-set path and the old `_scheduler_job_belongs_to_campaign` proxy. |
| `tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py` | Rebuilt focused disposable suite (23 cases) to the corrected contract. |
| `docs/printer-v1-...-migration-implementation.md` | This §13 (supersede). |

### 13.2 Exact Scheduler-state derivation (all scopes)

Every projection now reads the canonical `printer_scheduler_jobs` row and
derives the recorded ownership state from it via `_resolve_scheduler_state`:

- the recorded `work_state` **is** the real `printer_scheduler_jobs.status`;
- a caller-asserted `work_state` / `first_terminal_cause` / `terminal_at` are
  optional and are **rejected on any contradiction** with the canonical row;
- a terminal ownership state (`CANCELLED` / `FAILED` / `SUCCEEDED` / `SKIPPED`)
  can **never** be recorded while the real job is active (`PENDING` / `RUNNING`
  / `COOLDOWN`);
- terminal time comes from durable Scheduler evidence
  (`printer_discovery_work.terminal_at`) or `printer_scheduler_jobs.finished_at`;
  terminal cause from durable evidence, else `printer_scheduler_jobs.last_error`
  (FAILED), else the canonical token `SCHEDULER_JOB_<STATUS>`;
- exact-repeat idempotency preserves the existing row's stored actual state and
  first terminal cause (it returns before re-deriving).

### 13.3 Exact lineage source and target per scope

| Scope | Exact durable lineage source | Target category / identity |
| --- | --- | --- |
| `DISCOVERY_SELECTION` | `printer_discovery_work` row binding campaign/run/cycle/work identity/**exact `scheduler_job_id`** (selection is the `DISCOVERY_UNIFORM_SELECTION` work row on the same table) | `DISCOVERY_WORK` / `discovery_work_id` |
| `FIRST_15M_HANDOFF` | `printer_discovery_selected_item_links.first_window_15m_scheduler_job_id` == projected job, scoped to campaign/run/cycle, slot match | `SELECTED_ITEM`/`MERGED_CANDIDATE` matching the link |
| `WINDOW_LIFECYCLE` | exact campaign window/slot **and** campaign run whose `authoritative_run_id` == supplied `factory_run_id` **and** the factory run-step referencing the exact job | `CAMPAIGN_WINDOW` / `window_id` |
| `TERMINAL_CLEANUP` | immutable `SchedulerCleanupCapture` (from the campaign active-work owner) taken before cancellation + exact-scope durable owner | `SCHEDULER_JOB` / `str(scheduler_job_id)` |

Batch presence is no longer accepted for `DISCOVERY_SELECTION` (the
`printer_discovery_batches` / `printer_discovery_selection_links` proxies are
removed). Selection Scheduler jobs **do** have a durable exact linkage via
`printer_discovery_work.scheduler_job_id`, so no BLOCKED finding was required;
a selection job with no such linkage fails closed rather than falling back to a
batch proxy.

### 13.4 Strengthened cleanup capture

`SchedulerCleanupCapture` is a frozen, identity-bearing capture built by
`capture_campaign_active_scheduler_jobs()` from the existing campaign-scoped
active-work owner (`campaign_active_work.campaign_scoped_job_ids`), carrying
campaign/run/cycle, captured job ids, each **pre-cancellation** Scheduler state,
and a capture-boundary timestamp. Cleanup projection now validates: the job
belongs to the **exact** campaign/run/cycle (`_scheduler_job_in_exact_scope`,
tighter than the campaign-wide owner); the job was present in the capture with an
**active** pre-state (a capture taken after cancellation, or missing the job,
fails closed); the job's current Scheduler state is terminal and equals the
recorded ownership state; `target_category` is `SCHEDULER_JOB`; and
`target_identity` equals the exact job id. The untyped caller-supplied job-id set
is rejected. No second Scheduler-ownership table or authority was created.

### 13.5 Focused tests and output

Disposable databases only; 23 cases. Coverage of the required negative/positive
proofs: PENDING→CANCELLED blocks (`test_10`); terminal state/cause mismatch
blocks (`test_11`); discovery batch presence + unrelated job blocks (`test_12`);
selection owner + unrelated job blocks (`test_13`); cleanup foreign run/cycle
blocks (`test_14`); cleanup capture-after-cancel / missing pre-state / untyped
set blocks (`test_15`); cleanup target-identity mismatch blocks (`test_16`);
lifecycle factory-run-not-bound blocks (`test_17`, `test_17b`); lifecycle target
mismatch blocks (`test_18`); all four scopes lawful pass (`test_19`);
exact-repeat idempotent preserves state (`test_20`); migration preservation and
rollback remain green (`test_01`, `test_04`, `test_05`). Duplicate job,
competing identity, handoff-owner, schema-CHECK and immutability proofs retained.

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py -q
.......................                                                   [100%]
23 passed in 6.04s
```

Directly-affected ownership/Scheduler set:

```text
$ .venv/bin/python -m pytest \
    tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py \
    tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py \
    tests/test_v2_9_7d_6b_5_operational_lease_safe_stop.py \
    tests/test_v2_9_7d_6b_6_final_campaign_report.py \
    tests/test_v2_9_7e_42_direct_migration_discovery.py \
    tests/test_v2_9_1_proof_db_schema_readiness.py \
    tests/test_v2_9_7d_6b_2_operational_backup_restore_preflight.py -q
84 passed, 10 subtests passed in 15.70s
```

### 13.6 Pre-existing, out-of-scope failures (unchanged by this correction)

Verified failing identically **before and after** this correction (they depend
on migration `050` existing / an unrelated operational cleanup path, not on the
projection authority):

- `test_v2_9_8b_10_post_selection_lifecycle_integrity.py::...::test_migration_count_and_operational_factory_insert` — hard-codes the latest migration as `049` (stale snapshot, same class as the two noted in §8).
- `test_v2_9_7e_1_insufficient_pool_terminal_cleanup.py::...::test_insufficient_pool_cleanup_report_replay` — operational cleanup replay asserting `cancelled_scheduler_jobs >= 1`; fails identically on pristine HEAD `68d53ca`.

### 13.7 Schema decision

Keep migration `050` unchanged. The corrections are pure projection-authority
logic over the columns the migration already provides; no schema amendment is
genuinely required.

### 13.8 Corrected verdict

`V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_IMPLEMENTATION_PASS`

Exact Scheduler state and exact job lineage are now proven for all four scopes.
Authoritative data and operational paths were untouched: no migration applied to
the authoritative database, `data/printer_v1.sqlite3` never opened or mutated, no
provider/RPC/operational command run, and no later or financial capability
unlocked. A PASS still does not authorize applying `050` to the authoritative
database or resuming C1-C15; the next permitted lane remains the bounded
disposable migration proof.

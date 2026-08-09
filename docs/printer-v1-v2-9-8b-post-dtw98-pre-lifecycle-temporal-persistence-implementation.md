# Printer V1 — V2-9.8B Post-DTW98 Pre-Lifecycle Temporal Persistence Implementation

## Verdict

`V2_9_8B_POST_DTW98_PRE_LIFECYCLE_TEMPORAL_PERSISTENCE_IMPLEMENTATION_PASS`

Narrow implementation of the frozen post-DTW98 temporal-persistence design, proven
by focused offline TDD on disposable SQLite with an injected fake clock. It
authorizes nothing further.

## Baseline and final identity

- baseline branch:
  `agent/v2-9-8b-post-dtw98-pre-lifecycle-temporal-persistence-implementation`
- baseline HEAD (verified before any edit):
  `d459057752da229cdd33838cdad7c8adcf3fae6e`
- baseline tracked tree: clean
- design commit consumed: `d459057` (`Design bounded pre-lifecycle temporal persistence`)
- final implementation commit: the single commit on this branch whose parent is
  `d459057752da229cdd33838cdad7c8adcf3fae6e`. This document is committed inside
  it, so it cannot restate its own hash without invalidating it; read the exact
  final SHA and tree with `git log -1 --format='%H %T'`. The final SHA is also
  stated in the operator-facing completion message for this lane.

## Changed files

New:

- `migrations/054_pre_lifecycle_discovery_refresh_wait.sql`
- `src/printer_v1/discovery/pre_lifecycle_temporal_acquisition.py`
- `src/printer_v1/operator_cli/pre_lifecycle_temporal_refresh_owner.py`
- `tests/test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence.py`
- `docs/printer-v1-v2-9-8b-post-dtw98-pre-lifecycle-temporal-persistence-implementation.md`

Modified:

- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/campaign_active_work.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `tests/test_dtw90_pilot_input_readiness_route_migration.py`

Two new modules were added rather than growing the two large existing owners
(4,778 and 5,668 lines). The design's §11 file list is "expected", not
exhaustive; splitting keeps the canonical Scheduler orchestration in one
readable owner and the shared vocabulary/persistence in one contract module,
and avoids unrelated churn inside the campaign owner.

## What was built

1. **Bounded 900-second acquisition horizon.**
   `PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS = 900`, reusing the existing
   bounded discovery-only duration. It is separate from the post-supply
   lifecycle `duration_seconds = 1200` and from the 900s WINDOW_15M evidence
   window, and is persisted in the immutable campaign configuration plus the
   readiness ceilings block as
   `pre_lifecycle_acquisition_duration_seconds` and
   `total_wall_time_envelope_seconds`, so the longer possible wall-time envelope
   is explicit rather than hidden.

2. **Nonterminal `WAITING_FOR_ELIGIBLE_SUPPLY`.** Current-universe exhaustion
   with lawful horizon, budget, supervision and no pending refresh becomes a
   published, durably owned waiting state. `run_persistent_eligible_token_supply`
   returns `terminal = WAITING_FOR_ELIGIBLE_SUPPLY` with **no** shortage
   classification and **no** exhaustion certificate, because no shortage has
   been proven.

3. **Canonical Scheduler cadence, no private loop.** The owner takes its
   interval from `next_check_interval_seconds(JobKind.DISCOVERY_REFRESH)`
   (600s). `eligible_token_supply.py` contains no `enqueue_job` and no
   `claim_due_job`; the owner contains no sleep-polling, unbounded loop,
   background worker, subprocess or second child. Waiting is one bounded
   interruptible `Event.wait`.

4. **Exact pending-refresh ownership (migration 054).** One additive table,
   `printer_pre_lifecycle_discovery_refresh_waits`, binding a future-dated
   PENDING `DISCOVERY_REFRESH` job to the exact campaign/run/cycle/supervision
   before it is due. Unique per campaign/run/cycle/refresh-ordinal and per
   Scheduler job. Identity-immutability and no-terminal-reopen triggers. No
   source payload, ranking, score, confidence, weight or financial column.

5. **Claim-at-work-start preserved.**
   `enqueue -> due -> exact Scheduler claim -> discovery work RUNNING ->
   governed work -> terminalization`. A pending wait row is ownership evidence
   only; `printer_discovery_work` is created strictly after a successful claim
   and after exact claimed-job identity verification.

6. **Active-work and cleanup integration.** The wait table is now an exact-scope
   owner in `_job_has_exact_scope_owner`, contributes the
   `pre_lifecycle_refresh_wait_jobs` group, and
   `campaign_active_work_report` gained `active_pre_lifecycle_refresh_waits`,
   which is now part of `clean_terminal`. Batch presence alone is still not
   lineage.

7. **Reserve behaviour after waiting.** On a completed refresh every retained
   candidate is marked `ELIGIBLE_STALE`, removed from current capacity, and
   pushed back through the existing front-door revalidation focus. A retained
   candidate that fails is marked `REMOVED` with historical-only evidence. Only
   current, post-filter depth `>= 4` freezes. Tracking exclusions, exact-pair
   rules and the liquidity floor are untouched.

8. **Cumulative budget.** Refresh operations are added to the same invocation's
   `ops_used`. The 30-operation discovery budget is never reset after waiting;
   the owner refuses a stage that would exceed the remaining budget.

9. **Terminal precedence (fail-closed, ordered).** supervision failure ->
   cancellation/safe stop -> unsafe Scheduler/DB state -> source failure ->
   budget exhaustion -> acquisition deadline exhausted -> no lawful refresh
   window; otherwise waiting. A closed horizon is `DURATION_EXHAUSTION`, and
   `TRUE_MARKET_SUPPLY_SHORTAGE` is never emitted merely because one
   instantaneous universe was exhausted inside a live horizon.

10. **Certificate evidence.** `ExhaustionCertificate` gained an optional
    `pre_lifecycle_acquisition` block carrying started/deadline/elapsed/remaining
    seconds, opportunities scheduled/claimed/completed/cancelled, reserve depth
    transitions, revalidation outcomes, final current-universe state
    (`CURRENT_UNIVERSE_EXHAUSTED_WAITING` vs `..._TERMINAL`) and the controlling
    shortage classification. It is `None` for every non-temporal consumer.

11. **Deadline binding at the supply boundary.** The audit's Finding 2 gap is
    closed: when a temporal owner is supplied, `run_operational` now computes the
    acquisition deadline from `evaluated_at` and passes it as
    `deadline_at` into `supply_kwargs`, instead of leaving the eligible-supply
    loop with no horizon at all.

## RED evidence

The same test bodies were run against the baseline production tree before the
implementation was restored.

RED-A — full baseline production tree (`git stash push --include-untracked -- src migrations`):

```text
ImportError while importing test module
 '.../test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence.py'
E   ModuleNotFoundError: No module named
    'printer_v1.discovery.pre_lifecycle_temporal_acquisition'
ERROR tests/test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence.py
1 error in 0.13s
```

RED-B — new contract/owner modules present, but migration 054 removed from the
catalogue and all four integration edits reverted to baseline:

```text
22 failed, 2 passed in 6.55s
```

Every matrix case failed, including:

```text
FAILED ...::Migration054Tests::test_migration_054_adds_exactly_one_narrow_wait_table
FAILED ...::TemporalRefreshOwnerTests::test_case_01_three_of_four_exhausted_universe_is_nonterminal_waiting
FAILED ...::TemporalRefreshOwnerTests::test_case_02_exact_future_refresh_job_and_wait_row_are_persisted
FAILED ...::TemporalRefreshOwnerTests::test_case_03_before_due_claim_is_not_due_and_no_source_work_occurs
FAILED ...::TemporalRefreshOwnerTests::test_case_04_at_due_exact_claim_precedes_discovery_work_running
FAILED ...::TemporalRefreshOwnerTests::test_case_10_cancellation_while_waiting_leaves_zero_active_residue
FAILED ...::TemporalRefreshOwnerTests::test_case_11_supervision_failure_during_wait_aborts_without_source_work
FAILED ...::TemporalRefreshOwnerTests::test_case_12_active_work_owner_includes_pending_wait_job
FAILED ...::TemporalRefreshOwnerTests::test_case_13_foreign_wait_job_is_excluded
FAILED ...::TemporalRefreshOwnerTests::test_case_14_no_retry_restart_resume_successor_or_new_authorization
FAILED ...::TemporalSupplyIntegrationTests::test_case_01_supply_returns_nonterminal_waiting_not_shortage
FAILED ...::TemporalSupplyIntegrationTests::test_case_05_refresh_reveals_fourth_and_retained_three_revalidate
FAILED ...::TemporalSupplyIntegrationTests::test_case_06_retained_candidate_failing_revalidation_drops_capacity
FAILED ...::TemporalSupplyIntegrationTests::test_case_07_no_fitting_interval_before_horizon_is_duration_exhaustion
FAILED ...::TemporalSupplyIntegrationTests::test_case_08_cumulative_discovery_budget_does_not_reset_across_refresh
FAILED ...::TemporalSupplyIntegrationTests::test_case_09_source_failure_classification_is_unchanged
FAILED ...::TemporalSupplyIntegrationTests::test_case_15_zero_forbidden_capability_table_deltas
FAILED ...::TemporalSupplyIntegrationTests::test_case_16_existing_non_temporal_behaviour_is_unchanged
```

with `TypeError: run_persistent_eligible_token_supply() got an unexpected
keyword argument 'temporal_refresh_owner'` as the representative supply-side
cause. The only two RED-B passes were the pure horizon-arithmetic assertions
owned entirely by the new contract module.

## GREEN focused results

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence.py -q
........................                                                 [100%]
24 passed in 6.50s
```

All 16 design cases are covered:

| case | proof |
| --- | --- |
| 1 | `test_case_01_three_of_four_exhausted_universe_is_nonterminal_waiting` (boundary) and `test_case_01_supply_returns_nonterminal_waiting_not_shortage` (end to end) |
| 2 | `test_case_02_exact_future_refresh_job_and_wait_row_are_persisted` |
| 3 | `test_case_03_before_due_claim_is_not_due_and_no_source_work_occurs` |
| 4 | `test_case_04_at_due_exact_claim_precedes_discovery_work_running` |
| 5 | `test_case_05_refresh_reveals_fourth_and_retained_three_revalidate` |
| 6 | `test_case_06_retained_candidate_failing_revalidation_drops_capacity` |
| 7 | `test_case_07_no_fitting_interval_before_horizon_is_duration_exhaustion` |
| 8 | `test_case_08_cumulative_discovery_budget_does_not_reset_across_refresh` |
| 9 | `test_case_09_source_failure_classification_is_unchanged`, `test_refresh_stage_failure_is_source_availability_failure` |
| 10 | `test_case_10_cancellation_while_waiting_leaves_zero_active_residue` |
| 11 | `test_case_11_supervision_failure_during_wait_aborts_without_source_work` |
| 12 | `test_case_12_active_work_owner_includes_pending_wait_job` |
| 13 | `test_case_13_foreign_wait_job_is_excluded` |
| 14 | `test_case_14_no_retry_restart_resume_successor_or_new_authorization` |
| 15 | `test_case_15_zero_forbidden_capability_table_deltas` |
| 16 | `test_case_16_existing_non_temporal_behaviour_is_unchanged` |

Directly affected regression set:

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence.py \
  tests/test_v2_9_8b_21_eligible_token_supply_architecture.py \
  tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py \
  tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py \
  tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py \
  tests/test_dtw90_pilot_input_readiness_route_migration.py \
  tests/test_v2_9_8b_16_batch_scoped_discovery_persistence.py -q
1 failed, 147 passed, 1 skipped, 30 subtests passed in 185.45s
```

Safe-stop / active-work / ordinary-command regressions, each run **both** with
and without the change on the same tree:

```text
tests/test_v2_9_8b_window_15m_safe_stop_holder_accounting_repair.py
tests/test_v2_9_8b_post_handoff_terminal_compensation.py
  before: 7 failed, 38 passed      after: 7 failed, 38 passed     delta 0

tests/test_v2_9_8b_full_run_wiring_integration.py
tests/test_v2_9_8b_2_holder_budget_supervision_repair.py
  before: 1 failed, 18 passed      after: 1 failed, 18 passed     delta 0

tests/test_v2_9_8b_5_7_discovery_productivity.py
tests/test_v2_9_8b_19_production_readiness_consolidation.py
tests/test_v2_9_8b_pre_authorization_migration_ledger_drift_guard.py
tests/test_v2_9_8b_16_batch_scoped_discovery_persistence.py
  before: 33 failed, 70 passed     after: 35 failed, 68 passed    delta +2
```

Failure accounting, verified by stashing the production change and re-running
the identical selection on the same tree:

- Every failure except two is **pre-existing at baseline and byte-identical**.
- The two new failures are both in
  `tests/test_v2_9_8b_pre_authorization_migration_ledger_drift_guard.py`
  (`GuardBlockerTests::test_missing_migration_blocks`,
  `WrapperIntegrationTests::test_honest_live_binding_passes_the_real_guard`).
  That suite is already 19-failures broken at baseline because its fixtures are
  frozen at `052_...` while the live catalogue is at `053_...`. Migration 054
  extends the same pre-existing drift. **The guard is behaving correctly**: it
  is refusing an authorization whose applied ledger does not match the canonical
  catalogue. Repairing that suite's frozen fixtures needs the 053 drift fixed
  too and belongs to its own lane, not to this one. No gate, guard, evidence
  rule or assertion was weakened to hide it.
- `tests/test_dtw90_pilot_input_readiness_route_migration.py` was updated, not
  weakened: it now anchors `053_pilot_input_readiness_route_domain.sql` at its
  exact ordinal position 53 and asserts the live count exactly, instead of
  freezing the forward-only catalogue at this historical lane's head. Its
  integrity, foreign-key and ledger-match assertions are unchanged.

Broad suites were deliberately not run. Per `AGENTS.md` Risk-Based Verification,
broad regression is reserved for lane closeout / pre-live readiness, which is a
later lane.

## Migration / schema result

- `054_pre_lifecycle_discovery_refresh_wait.sql` applies cleanly to a fresh
  disposable database; `PRAGMA integrity_check` = `ok`, `PRAGMA
  foreign_key_check` = empty.
- Canonical migration count moved `53 -> 54`; ordinals remain contiguous and the
  catalogue digest recomputes from the live directory (never hard-coded).
- The migration is purely additive and forward-only. **No applied migration was
  edited.** No existing table, index, trigger or row is read, rebuilt, altered
  or dropped.
- It was applied only to disposable test databases. **It was not applied to the
  authoritative database.**

## Money-usefulness contribution

DTW98 spent a one-use authorization and stopped at 3 of 4 eligible identities
with 16 source operations still lawful, zero provider failures and no hard
ceiling reached — a snapshot result, not a proven market shortage. Printer can
now spend bounded *time* instead of another one-use authorization to bridge that
gap: one Scheduler-owned 600-second refresh inside a 900-second horizon, inside
the same campaign, with the retained reserve revalidated rather than assumed.
That raises the probability of reaching a valid, current, diverse four-deep
WINDOW_15M memory set without lowering a single evidence gate — and the memories
that set produces are what later retrieval and paper decisions depend on.

## What improved

- instantaneous universe exhaustion is no longer conflated with true market
  shortage while a lawful future refresh remains;
- waiting is Scheduler-owned, durably attributable and auditable, not a timer
  side effect;
- the previously unbound eligible-supply deadline is bound at the supply
  boundary with its own explicit horizon, not by stealing lifecycle time;
- a pending future refresh is visible to safe stop and cleanup before it is due,
  without fabricating discovery work;
- the prior 3-of-4 reserve is useful retained evidence, never an entitlement;
- the total one-shot wall-time envelope is stated in configuration and readiness
  reporting instead of being an implicit surprise.

## What remains locked

No source, runtime, proof, or authorization capability is unlocked here.
WINDOW_1H/4H/12H/24H, retrieval activation, clean-memory creation, paper
decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, live
execution, wallets, private keys, real funds, paid APIs, scoring, ranking,
confidence percentages, weighted logic, embeddings and vectors all remain
locked. `WINDOW_5M_MICRO_EVENT` remains support-only. DTW98 remains permanently
consumed and non-reusable. Zero forbidden capability-table deltas were observed
in every focused case.

## Proof still required

1. bounded disposable proof lane for this implementation (not run here);
2. repair closeout;
3. applying migration 054 to the authoritative database under its own
   authorized migration lane — until then the pre-authorization ledger guard
   will correctly block WINDOW_15M authorization on
   `migration_count_mismatch` / `migration_head_mismatch`;
4. a live Source-Governed refresh stage and discovery-batch resolver for the
   operational wiring — this lane injects both and proves the contract offline,
   but does not build the live stage;
5. fresh authoritative rereadiness;
6. a fresh exact-HEAD one-use authorization;
7. one separately operator-approved ordinary WINDOW_15M attempt, host-awake
   under `caffeinate -dimsu`;
8. independent campaign closeout.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Migration-ledger guard will block authorization until 054 is applied.** This
  is correct fail-closed behaviour, but it is a hard prerequisite before any
  future WINDOW_15M attempt, and it is not satisfied by this lane.
- **Applied-schema constraint on refresh work rows.**
  `printer_discovery_batches` is UNIQUE per `cycle_id` and
  `printer_discovery_work` is UNIQUE `(discovery_batch_id, work_type)`. Exactly
  one temporal refresh work row can therefore exist per cycle. That matches the
  900s horizon's single refresh opportunity, but it means the refresh work type
  (`DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE`) must not collide with another
  stage writing the same type into the same cycle's batch. A collision fails
  closed at the database rather than silently overwriting — but it *is* a
  latent integration hazard for the live wiring lane. Widening the work-type
  vocabulary would require rebuilding an applied table and was correctly out of
  scope here.
- **The owner carries an acquisition high-water mark.** A completed refresh
  really consumed one interval, so the next window is measured from the woken
  instant. Without this the horizon would silently admit more than one refresh.
  It is deliberate, and it makes the "exactly one refresh" law testable.
- 900 seconds permits only one normal 600-second refresh. This is the intended
  minimum scope and may still honestly exhaust with a 3-of-4 reserve.
- Total wrapper wall time can now reach roughly 2,100 seconds
  (900 acquisition + 1,200 lifecycle). No source-operation or financial ceiling
  increased.
- Reserve revalidation consumes scarce source budget from the same cumulative
  30-operation pool; a refresh that reveals nothing still costs operations.
- The campaign heartbeat must stay healthy across the wait; the owner aborts on
  observed supervision failure or cancellation and never waits blindly past it.
- Expanding cadence, horizon, source ceilings or eligibility rules to obtain a
  PASS remains prohibited and was not done.

## Confirmation of untouched authorities

- **Authoritative database:** not opened, not read, not migrated, not mutated.
  Every test used a disposable `tempfile` SQLite database. Migration 054 was
  applied only to those.
- **Sources/providers:** zero provider calls, zero network access. Discovery,
  liquidity and refresh transports were injected fixtures; the refresh stage is
  a dependency-injected callable and the tests supply a local one that performs
  no I/O.
- **Printer runtime:** no Printer runtime, no campaign, no Source Governor
  runtime, no Central Scheduler runtime outside disposable in-test databases.
- **Authorization:** no authorization created, consumed, reused or simulated. No
  manifest, no application marker, no wrapper child, no WINDOW_15M execution.
- **Real sleep:** none. `bounded_interruptible_wait` was exercised only with a
  pre-set `threading.Event` and a zero timeout; every timed path used an
  injected fake clock and an immediate waiter.
- **Memory:** no memory generated, no window closed, no retrieval, no decision.

## Next lane

`V2-9.8B Post-DTW98 Pre-Lifecycle Temporal Persistence Bounded Proof`

Stop here. This lane does not authorize the bounded proof lane, rereadiness,
authorization creation, or WINDOW_15M execution.

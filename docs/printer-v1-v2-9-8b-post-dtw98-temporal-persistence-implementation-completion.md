# Printer V1 — V2-9.8B Post-DTW98 Temporal Persistence Implementation Completion

## Verdict

`V2_9_8B_POST_DTW98_PRE_LIFECYCLE_TEMPORAL_PERSISTENCE_IMPLEMENTATION_COMPLETION_PASS`

The missing ordinary production wiring identified by
`V2_9_8B_POST_DTW98_TEMPORAL_PERSISTENCE_IMPLEMENTATION_REVIEW_BLOCKED_LIVE_WIRING_INCOMPLETE`
is complete. The ordinary WINDOW_15M composition now constructs exactly one
exact-scope `PreLifecycleTemporalRefreshOwner` and passes it into
`run_operational`, so ordinary 3-of-4 instantaneous-universe exhaustion becomes
`WAITING_FOR_ELIGIBLE_SUPPLY` instead of immediate terminalization.

This lane authorizes nothing further.

## Baseline and final identity

- baseline branch:
  `agent/v2-9-8b-post-dtw98-temporal-persistence-implementation-completion`
- baseline HEAD (verified before any edit):
  `60ad520846a3e25e402fb15a45721e6bda8f2a14`
- baseline tracked tree: clean
- preserved implementation commit: `078e2e83db4d9fcbb6cd32f1774eeb6bfea67279`
  (verified as an ancestor of the baseline; not redesigned)
- consumed review commit: `60ad520` (`Review temporal persistence implementation wiring gap`)
- final implementation-completion commit: the single commit on this branch whose
  parent is `60ad520846a3e25e402fb15a45721e6bda8f2a14`. This document is
  committed inside it, so it cannot restate its own hash; read the exact final
  SHA and tree with `git log -1 --format='%H %T'`.

## Changed files

New:

- `src/printer_v1/discovery/pre_lifecycle_refresh_composition.py`
- `tests/test_v2_9_8b_post_dtw98_temporal_persistence_completion.py`
- `docs/printer-v1-v2-9-8b-post-dtw98-temporal-persistence-implementation-completion.md`

Modified:

- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/pre_lifecycle_temporal_refresh_owner.py`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/discovery/pre_lifecycle_temporal_acquisition.py`
- `tests/test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence.py`

No migration was added or edited in this lane. Migration 054 is unchanged from
`078e2e83`.

## What was built

### 1. Exactly one owner in the real ordinary composition

`_build_pre_lifecycle_temporal_refresh_owner(...)` composes the owner in
`operational_memory_factory_command.py` and the ordinary `run_operational` call
site passes it. Everything it binds already existed and is reused verbatim:

- the exact authorized `campaign_id` / `run_id` / `cycle_id` / `supervision_id`;
- `OwnerPort(SOURCE_GOVERNOR_OWNER, True)` and
  `OwnerPort(CENTRAL_SCHEDULER_OWNER, True)` — the same ports the campaign uses;
- the existing `_CampaignHeartbeat.failure_event` as the prompt wait-abort
  boundary and the existing `cancellation_probe` as the supervision/safe-stop
  probe. The heartbeat itself was **not** modified;
- the 900-second horizon from
  `policy.pre_lifecycle_acquisition_duration_seconds`, the same value already
  recorded in the immutable campaign configuration.

The supervision adapter keeps the two conditions categorically distinct: a
failed lease is `supervision_active=False`, never a cooperative cancellation.

### 2. Live refresh stage from approved owners only

`build_pre_lifecycle_refresh_stage(...)` composes exactly the two existing
approved owners the ordinary permanent-availability supply already runs at
campaign start, in the same order, with the same accounting:

1. `run_geckoterminal_fresh_nomination` — one governed free/public
   GeckoTerminal `new_pools` request (the stage
   `DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE` names);
2. `process_protocol_confirmation_queue` — the existing governed PumpSwap
   account-batch confirmation/promotion owner.

No new discovery engine, provider, adapter, gate, selector, score, rank or
weight is introduced. Promotion decisions stay with the protocol-confirmation
owner; admission, revalidation, the front door and the four-deep freeze stay
with `eligible_token_supply`. The stage refuses to run when no lawful operation
remains and never returns more than `source_operations_remaining`.

### 3. Promotions admitted through the existing path

The campaign-start promotion shape was extracted into
`_protocol_promotion_candidate(...)` and is now shared verbatim by the
campaign-start early-protocol pass and the temporal refresh, so a second
admission gate cannot drift into existence. A refresh promotion never restores a
retained candidate that is mid-revalidation, and — matching the existing path
exactly — it does not write the durable eligible reserve.

### 4. `(cycle_id)` collision hazard resolved by construction

`printer_discovery_batches` is UNIQUE on `cycle_id`, so a cycle owns exactly one
batch and a pre-lifecycle writer could previously have collided with the
combined executor. Resolved with one shared derivation in `combined_executor`:

- `canonical_cycle_discovery_batch_id(...)`;
- `ensure_cycle_discovery_batch(...)` — create-or-reuse, idempotent for a
  byte-identical canonical payload (`batch_state` is outside the canonical
  hash);
- `resolve_campaign_selection_seed(...)` — one seed precedence for every writer.

`_run_cycle` now routes through `ensure_cycle_discovery_batch` and fails closed
on `SHARED_SELECTION_SEED_MISMATCH`, and
`operational_discovery_batch_identity_inputs()` gives the command the same
provider-contract versions and git identity `_build_fixtures` uses. Whichever
lawful owner reaches the cycle first creates the batch; the other reuses it. No
applied table was rebuilt and no ownership rule was weakened.

### 5. `(discovery_batch_id, work_type)` collision hazard resolved fail-closed

All eleven `work_type` values are reachable by the executor in some branch, so a
"safe" type cannot be chosen by construction. Instead the owner now checks the
slot **before** consuming its claim and, if the slot is owned, terminalizes its
own job and wait row as `PRE_LIFECYCLE_REFRESH_WORK_SLOT_TAKEN` with zero active
residue. It never steals, rewrites or overwrites another owner's work row.

## RED evidence

Same test bodies, run against the review baseline.

RED-A — full baseline production tree (`git stash push --include-untracked -- src`):

```text
ImportError while importing test module
 '.../test_v2_9_8b_post_dtw98_temporal_persistence_completion.py'
E   ImportError: cannot import name 'canonical_cycle_discovery_batch_id'
    from 'printer_v1.discovery.combined_executor'
ERROR tests/test_v2_9_8b_post_dtw98_temporal_persistence_completion.py
1 error in 0.11s
```

RED-B — everything restored **except** the ordinary command wiring, isolating
precisely the defect the review named:

```text
6 failed, 10 passed in 4.67s

FAILED ...::OrdinaryCompositionWiringTests::test_ordinary_call_site_passes_a_constructed_owner_not_none
FAILED ...::OrdinaryCompositionWiringTests::test_command_module_exposes_exactly_one_owner_construction
FAILED ...::ProductionOwnerConstructionTests::test_production_builder_returns_exact_scope_bound_owner
FAILED ...::ProductionOwnerConstructionTests::test_supervision_probe_maps_heartbeat_and_cancellation_separately
FAILED ...::ProductionOwnerConstructionTests::test_heartbeat_failure_event_is_the_wait_abort_boundary
FAILED ...::ProductionOwnerConstructionTests::test_run_operational_forwards_owner_and_horizon_to_supply
```

with `AttributeError: module
'printer_v1.operator_cli.operational_memory_factory_command' has no attribute
'_build_pre_lifecycle_temporal_refresh_owner'` as the representative cause. The
ten passing cases are the composition/batch/refresh/supply proofs whose modules
were restored — which is exactly the review's finding that the machinery existed
and only the production boundary was missing.

An additional genuine RED was found and fixed **during** this lane: the first
version of the proof used a DexScreener-shaped fixture for the GeckoTerminal
transport, so the production nomination silently returned
`status: FAILED, nominations accepted: 0` while the test still passed on a
weaker assertion. The fixture was corrected to the real `new_pools` contract and
the assertions were tightened to require `COMPLETE` status, a named nomination
and a named promotion, so proof 5 cannot pass hollow.

## GREEN focused results

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_post_dtw98_temporal_persistence_completion.py \
  tests/test_v2_9_8b_post_dtw98_pre_lifecycle_temporal_persistence.py -q
........................................                                 [100%]
40 passed in 12.01s
```

Required minimum proof coverage:

| # | requirement | proof |
| --- | --- | --- |
| 1 | ordinary composition constructs a non-null exact-scope owner | `test_ordinary_call_site_passes_a_constructed_owner_not_none`, `test_command_module_exposes_exactly_one_owner_construction`, `test_production_builder_returns_exact_scope_bound_owner`, `test_run_operational_forwards_owner_and_horizon_to_supply` |
| 2 | 3/4 exhaustion reaches WAITING | `test_proof_02_three_of_four_exhaustion_reaches_waiting` |
| 3 | before due: zero refresh source calls | `test_proof_03_before_due_the_production_stage_issues_no_request` |
| 4 | at due: exact claim precedes discovery-work RUNNING | `test_proof_04_and_09_due_refresh_claims_then_records_governed_requests` |
| 5 | production composition exposes a fourth candidate | `test_proof_05_06_07_10_refresh_exposes_fourth_and_freezes_two_plus_two` |
| 6 | retained three revalidate before 2+2 freeze | same, plus `test_proof_06_retained_candidate_failing_revalidation_drops_capacity` |
| 7 | cumulative budget does not reset | same (proof 5 test, budget section) |
| 8 | cancellation/heartbeat failure leaves zero residue | `test_proof_08_cancellation_leaves_zero_residue_through_production_owner`, `test_heartbeat_failure_event_is_the_wait_abort_boundary` |
| 9 | source-request accounting remains exact | `test_proof_04_and_09_...` (`outcome.source_operations == governed request count`) |
| 10 | no forbidden capability deltas | `assertNoForbiddenCapabilityDelta` across the suite |
| 11 | affected regressions show no new failures | see below |

Proof 5 is genuinely end to end: the unmodified production composition, driven
only by two injected approved transports, issues `geckoterminal_new_pool_discovery`
and `pumpswap_pool_account_batch` governed requests, the protocol-confirmation
owner promotes the newly reachable mint, the retained three revalidate through
the front door, and the result is an exact four-deep 2-selected + 2-alternate
freeze. Nothing test-side seeds the fourth candidate.

### Regression set (proof 11)

```text
tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py
tests/test_v2_9_7d_7b_5_isolated_combined_discovery_proof.py
tests/test_v2_9_7d_7b_4c_discovery_persistence.py
tests/test_v2_2v_discovery_persistence_gate_reform.py
tests/test_v2_9_8a_scheduler_residue_reconciliation.py
  77 passed, 45 subtests passed                                   delta 0

tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py
tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration.py
tests/test_v2_9_8b_campaign_scheduler_ownership_schema_migration_bounded_proof.py
tests/test_v2_9_8b_full_run_wiring_integration.py
tests/test_v2_9_8b_2_holder_budget_supervision_repair.py
tests/test_dtw90_pilot_input_readiness_route_migration.py
  1 failed, 112 passed, 1 skipped, 30 subtests passed             delta 0

tests/test_v2_9_8b_16_batch_scoped_discovery_persistence.py
tests/test_v2_9_8b_permanent_discovery_availability.py
tests/test_v2_9_8b_governed_pumpswap_account_batch_confirmation.py
tests/test_v2_9_8b_21_eligible_token_supply_architecture.py
  before: 2 failed, 75 passed      after: 2 failed, 75 passed     delta 0
```

Every failure is pre-existing at `60ad520` and byte-identical with the change
stashed and restored on the same tree:

- `test_v2_9_8b_2_holder_budget_supervision_repair.py::...base_work_is_rejected_with_exact_values`
  — `KeyError: 'base_operations'`, unrelated to this lane;
- `test_v2_9_8b_16_batch_scoped_discovery_persistence.py::test_safe_fault_details_reach_terminal_evidence`
  — pre-existing;
- `test_v2_9_8b_permanent_discovery_availability.py::TestMigration051::test_upgrade_from_050_applies_forward_cleanly`
  — asserts the catalogue head is `052_...`; it already failed at `60ad520`
  because migration 054 landed in `078e2e83`. It is the same frozen-head family
  as the pre-authorization ledger guard suite and is deferred to the separate
  migration-054 lane rather than loosened here.

No test, gate, guard, evidence rule or assertion was weakened. Broad suites were
not run: per `AGENTS.md` Risk-Based Verification, broad regression belongs to
lane closeout / pre-live readiness.

## Risks, setbacks and efficiency blockers

- **Migration 054 still blocks authorization.** It remains unapplied to the
  authoritative database by design. The pre-authorization ledger guard will
  correctly refuse WINDOW_15M authorization on `migration_count_mismatch` /
  `migration_head_mismatch` until the separate migration-054 readiness/
  application/proof/closeout lane runs. That sequencing is intentional.
- **Frozen-head test suites will keep failing until that lane.** Two suites
  assert the catalogue ends at `052_...`. They were already failing at this
  lane's baseline and are not this lane's to repair.
- **One refresh work slot per cycle.** `UNIQUE (discovery_batch_id, work_type)`
  plus one batch per cycle means exactly one temporal refresh work row per
  cycle. That matches the 900-second horizon's single refresh opportunity, but a
  second one fails closed rather than proceeding.
- **`DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE` is shared vocabulary.** The
  ordinary graduated path uses the retained-evidence lane and never writes that
  type, so the slot is free in practice; if a future change routes the ordinary
  path down the secondary lanes instead, the pre-claim slot check fails the
  refresh closed rather than corrupting the batch. Widening the work-type
  vocabulary needs an applied-table rebuild and stays out of scope.
- **Cancellation latency is bounded by the refresh interval.** The heartbeat
  failure event aborts the wait immediately; a cooperative safe-stop flag
  written to the database is observed at wake, so worst-case observation latency
  is the canonical 600 seconds. No polling loop was added to shorten it.
- **Unknown-liquidity nominations do not promote in a refresh.** The composition
  deliberately stops at two owners; a nomination lacking proven liquidity simply
  does not reach protocol confirmation. That is fail-closed and honest.
- **Total wall time.** Ordinary one-shot wall time can now reach roughly 2,100
  seconds (900 acquisition + 1,200 lifecycle). No source-operation or financial
  ceiling increased.
- **A refresh consumes scarce budget.** Up to two governed operations come out
  of the same cumulative 30-operation discovery budget, which never resets.

## Confirmation of untouched authorities

- **Authoritative database:** not opened, not read, not migrated, not mutated.
  Every test used a disposable `tempfile` SQLite database. Migration 054 was
  applied only to those and remains unapplied to the authoritative database.
- **Sources/providers:** zero network access and zero live provider calls. Every
  provider request in the proof went through the Source Governor against an
  injected approved fixture transport (`geckoterminal_new_pool_discovery`,
  `pumpswap_pool_account_batch`).
- **Printer runtime:** no campaign, no WINDOW_15M execution, no memory
  generated, no window closed, no retrieval, no decision.
- **Authorization:** none created, consumed, reused or simulated. No manifest,
  no application marker, no wrapper child.
- **Real sleep:** none. Every timed path used an injected fake clock and an
  immediate waiter; the abort boundary was exercised with a pre-set
  `threading.Event`.
- **Frozen design:** unchanged. The `078e2e83` implementation was preserved and
  completed, not redesigned.

## Next lane

`V2-9.8B Post-DTW98 Pre-Lifecycle Temporal Persistence Bounded Proof`

Stop here. This lane does not authorize the bounded proof lane, authoritative
migration-054 application, rereadiness, authorization creation, or WINDOW_15M
execution.

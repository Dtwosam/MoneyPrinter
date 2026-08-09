# Printer V1 — V2-9.8B Post-DTW98 Temporal Persistence Bounded Disposable Proof

## Verdict

`V2_9_8B_POST_DTW98_PRE_LIFECYCLE_TEMPORAL_PERSISTENCE_BOUNDED_PROOF_PASS`

The ratified implementation is proven on disposable SQLite with injected
approved transports and an injected fake clock. Nothing further is authorized.

## Baseline and final identity

- baseline branch:
  `agent/v2-9-8b-post-dtw98-temporal-persistence-bounded-proof`
- baseline HEAD (verified before any edit):
  `0ade79f8c31c6d1d32cc7142427671fa7cd80109`
- baseline tracked tree: clean
- ratified implementation under proof:
  `96e755700cd877a3e0da9bac060adede853c1421` (verified as an ancestor)
- consumed ratification: `0ade79f` (`Ratify completed pre-lifecycle temporal
  persistence implementation`)
- final bounded-proof commit: the single commit on this branch whose parent is
  `0ade79f8c31c6d1d32cc7142427671fa7cd80109`. This document is committed inside
  it and cannot restate its own hash; read it with
  `git log -1 --format='%H %T'`.

## Exact disposable proof database identity

Every database in this lane is created by `tempfile.TemporaryDirectory()` and
destroyed at teardown. One representative freshly-migrated instance:

| field | value |
| --- | --- |
| basename | `bounded-proof.sqlite3` |
| location | ephemeral `tempfile` directory (asserted) |
| sha256 | `4c29409566b7beacb8b0cf31539b3c72d256ad8afb8b177a354cf003306f1a94` |
| size | `2,781,184` bytes |
| migration count | `54` (equals live canonical count) |
| migration head | `054_pre_lifecycle_discovery_refresh_wait.sql` |
| `PRAGMA integrity_check` | `ok` |
| `PRAGMA foreign_key_check` | `0` violations |
| equals `CANONICAL_PERSISTENT_DB` | `False` (asserted) |

The sha256 is asserted to be a valid 64-hex digest on every run but is not
stable across runs, because `printer_schema_migrations.applied_at` records real
application time. The schema-level identity above (count, head, integrity, FK)
is the stable, meaningful identity and is asserted every run.

`CANONICAL_PERSISTENT_DB` appears in the proof module **only** as a value to
assert inequality against. It is never opened, read, written or migrated.

## Proof cases and results

New proof-specific cases, added only where the existing focused suites left a
genuine gap:

```text
.venv/bin/python -m pytest \
  tests/test_v2_9_8b_post_dtw98_temporal_persistence_bounded_proof.py -q
......                                                                   [100%]
6 passed in 1.59s
```

Full temporal set (bounded proof + completion + focused implementation):

```text
46 passed in 13.66s
```

| # | requirement | result | evidence |
| --- | --- | --- | --- |
| 1 | migration 054 applies cleanly; integrity `ok`; FK `0` | PASS | `test_proof_01_migration_054_applies_cleanly_with_clean_integrity` — head `054`, count `54`, both guard triggers present |
| 2 | ordinary composition builds exactly one exact-scope owner | PASS | completion suite `OrdinaryCompositionWiringTests`, `test_production_builder_returns_exact_scope_bound_owner` |
| 3 | 3/4 + universe exhaustion enters `WAITING_FOR_ELIGIBLE_SUPPLY` | PASS | `test_proof_02_three_of_four_exhaustion_reaches_waiting` |
| 4 | future `DISCOVERY_REFRESH` durably owned by exact campaign/run/cycle | PASS | `test_case_02_exact_future_refresh_job_and_wait_row_are_persisted`, `test_case_12/13` (exact scope in, foreign scope out) |
| 5 | zero refresh source operations before due | PASS | `test_proof_03_before_due_the_production_stage_issues_no_request` — `printer_source_requests` = 0, no work row |
| 6 | claim → wait CLAIMED → slot check → work RUNNING → governed work | PASS | `test_proof_06_ordered_claim_wait_slot_work_then_governed_work` |
| 7 | governed nomination + PumpSwap confirmation expose a fourth candidate | PASS | accounting record: nomination `COMPLETE`, 1 nomination, 1 promotion |
| 8 | retained three revalidated before any 4/4 freeze | PASS | accounting record `retained_marked_stale = 3`; `test_proof_06_retained_candidate_failing_revalidation_drops_capacity` |
| 9 | exact 2 selected + 2 alternates freeze | PASS | `eligible_reserve_count = 4`, `terminal = GRADUATED_SUPPLY_READY` |
| 10 | cumulative 30-operation budget never resets | PASS | `budget 30`, `used 14`, `remaining 16` (exactly `30 − 14`) |
| 11 | 900s horizon permits one refresh then duration-exhausts honestly | PASS | `test_proof_11_one_refresh_then_horizon_exhausts_honestly` |
| 12 | occupied work slot fails closed after claim, zero residue | PASS | `test_proof_12_occupied_slot_fails_closed_after_claim` |
| 13 | cancellation and heartbeat/supervision failure clean all state | PASS | `test_case_10`, `test_case_11`, `test_proof_08_cancellation_leaves_zero_residue_through_production_owner` |
| 14 | no retry/restart/resume/successor/new authorization | PASS | `test_case_14_no_retry_restart_resume_successor_or_new_authorization` |
| 15 | zero forbidden capability-table deltas | PASS | `forbidden_capability_rows = 0` across every case |
| 16 | migration 054 unapplied to the authoritative DB | PASS | `test_proof_16_proof_database_is_disposable_and_not_authoritative`; `git status -- data/` clean |

### Case 6 — the ratified order, asserted as implemented

The ratification corrected the completion report's wording about when the
work-slot check runs. This proof asserts the **actual** order, observed at the
instant governed refresh work is permitted to begin:

```text
due -> exact Scheduler claim (job RUNNING)
    -> claimed identity verification
    -> wait row CLAIMED
    -> canonical cycle batch resolve
    -> (discovery_batch_id, work_type) slot check
    -> discovery work RUNNING
    -> Source-Governed refresh work
```

Observed values inside the stage: `job_status = RUNNING`,
`wait_state = CLAIMED`, `work_state = RUNNING`,
`work_type = DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE`, work batch equal to the
canonical cycle batch, and `source_requests_before_governed_work = 0`. All three
owners then terminalize consistently as `SUCCEEDED`.

The misleading source comment that claimed the slot check happens *before* the
claim was corrected in this lane. The code was already correct; only the comment
was wrong.

### Case 11 — honest exhaustion, proven for the right reason

An empty GeckoTerminal page is classified by the existing adapter as
`geckoterminal_no_valid_solana_pools`, i.e. a **provider failure** — which would
have proven source-availability handling, not horizon exhaustion. The proof
therefore uses a lawful refresh that genuinely completes but exposes nothing
newly eligible: a nominated pool truthfully below the categorical `$3,000`
floor.

Observed: `nomination status COMPLETE`, `failure_type None`,
`provider_failures 0`, one nomination accepted with prefilter outcome
`BELOW_LIQUIDITY_FLOOR`, `promoted 0`, capacity remains `3/4`, and the terminal
is `DURATION_EXHAUSTION` — never `TRUE_MARKET_SUPPLY_SHORTAGE` and never a
fabricated source failure. Exactly one refresh opportunity was scheduled and
claimed; a second 600-second interval does not fit inside the 900-second
horizon.

## Scheduler, source and budget accounting

Full-scenario record from the successful 3/4 → 4/4 path:

| quantity | value |
| --- | --- |
| Scheduler jobs created | 1 (`DISCOVERY_REFRESH`, terminal `SUCCEEDED`) |
| refresh wait rows | 1 (ordinal 1, terminal `SUCCEEDED`) |
| discovery work rows | 1 (`DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE`, `SUCCEEDED`) |
| temporal refresh opportunities scheduled / claimed / completed | 1 / 1 / 1 |
| governed source requests, total | 14 |
| discovery operations used | 14 |
| discovery operation budget | 30 |
| discovery operations remaining | 16 |
| refresh-stage source operations | 2 |
| governed refresh request kinds | `geckoterminal_new_pool_discovery` ×1, `pumpswap_pool_account_batch` ×1 |
| retained candidates marked stale for revalidation | 3 |
| eligible reserve after freeze | 4 (exact 2 selected + 2 alternates) |
| active jobs after terminal | 0 |
| active pre-lifecycle refresh waits after terminal | 0 |
| `clean_terminal` | `True` |
| forbidden capability-table rows | 0 |

`governed_requests_total` (14) equals `discovery_operations_used` (14) exactly:
source accounting is request-identical, and the refresh's two operations are
added to the same cumulative budget rather than resetting it. The remaining
twelve requests are the supply's own front-door market work
(`pair_market_snapshot`, `restored_pump_migration_signature_page`), unchanged by
this lane.

In the horizon-exhaustion scenario the refresh consumed one governed operation
(`13` used, `17` remaining) and still terminalized honestly.

## Integrity and foreign-key result

`PRAGMA integrity_check` = `ok` and `PRAGMA foreign_key_check` = `0` violations
on every freshly-migrated disposable proof database, with foreign keys enforced
(`PRAGMA foreign_keys=ON`) throughout. Migration 054 is additive and
forward-only; no existing table was rebuilt.

## Regression set

```text
tests/test_v2_9_8b_16_batch_scoped_discovery_persistence.py
tests/test_v2_9_8b_permanent_discovery_availability.py
tests/test_v2_9_8b_governed_pumpswap_account_batch_confirmation.py
tests/test_v2_9_8b_21_eligible_token_supply_architecture.py
tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py
tests/test_v2_9_8a_scheduler_residue_reconciliation.py
  before: 2 failed, 89 passed      after: 2 failed, 89 passed      delta 0
```

Unrelated pre-existing failures, recorded separately and byte-identical with the
change stashed and restored on the same tree:

1. `test_v2_9_8b_16_batch_scoped_discovery_persistence.py::BatchScopedDiscoveryPersistenceProof::test_safe_fault_details_reach_terminal_evidence`
   — pre-existing, unrelated to temporal persistence.
2. `test_v2_9_8b_permanent_discovery_availability.py::TestMigration051::test_upgrade_from_050_applies_forward_cleanly`
   — asserts the catalogue head is `052_...`. Frozen-head fixture drift; it
   already failed before migration 054 existed in this branch's history and
   belongs to the later migration-054 lane, exactly as the ratification directs.

No broad suite was run: no proof failure required it, and `AGENTS.md`
Risk-Based Verification reserves broad regression for lane closeout and pre-live
readiness. No test, gate, guard, evidence rule or assertion was weakened.

## Money-usefulness contribution

DTW98 burned a one-use authorization and stopped at 3 of 4 eligible identities
with 16 governed operations still lawful and zero provider failures — a snapshot
result, not a proven market shortage. This proof demonstrates, on disposable
infrastructure, that Printer can now spend bounded *time* instead of another
authorization: one Scheduler-owned 600-second refresh inside a 900-second
horizon, inside the same campaign, revalidating the retained reserve rather than
assuming it, reaching a genuine four-deep 2+2 freeze for 14 of 30 operations.
It also demonstrates the honest negative: when nothing newly eligible appears,
the run duration-exhausts truthfully instead of manufacturing a market-shortage
verdict. Both outcomes protect the quality of the WINDOW_15M memories that later
retrieval and paper decisions depend on.

## What this proves

- migration 054 applies cleanly and leaves a clean, FK-consistent schema;
- the real ordinary composition constructs exactly one exact-scope temporal
  owner and reaches the supply boundary with it;
- instantaneous universe exhaustion at 3/4 is nonterminal while a lawful future
  refresh remains;
- a pending future refresh is durably owned by the exact campaign/run/cycle and
  is invisible to foreign scopes;
- waiting performs zero provider operations;
- claim-at-work-start holds in the exact ratified order;
- the production refresh composition, built only from approved owners, can
  expose a fourth candidate through governed requests;
- retained candidates cannot count until revalidated;
- the cumulative 30-operation budget never resets;
- the 900-second horizon admits exactly the one designed refresh and then
  exhausts honestly;
- an occupied work slot fails closed after claim without work, source calls or
  residue, and without touching the other owner;
- cancellation and heartbeat failure leave zero active wait/job/work residue;
- zero forbidden capability-table deltas throughout.

## What remains locked

Nothing is unlocked here. Migration 054 remains unapplied to the authoritative
database. WINDOW_15M execution, WINDOW_1H/4H/12H/24H, retrieval activation,
clean-memory creation, paper decisions, BUY/SELL/HOLD, positions, trade events,
paper audits, PnL, live execution, wallets, private keys, real funds, paid APIs,
scoring, ranking, confidence percentages, weighted logic, embeddings and vectors
all remain locked. `WINDOW_5M_MICRO_EVENT` remains support-only. DTW98 remains
permanently consumed and non-reusable.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Migration 054 is still a hard authoritative prerequisite.** Until a separate
  authorized migration-054 lane applies it, the pre-authorization ledger guard
  will correctly block WINDOW_15M authorization on `migration_count_mismatch` /
  `migration_head_mismatch`. This proof deliberately does not satisfy that.
- **Frozen migration-head fixtures stay red** until that lane. Two suites assert
  a `052` catalogue head; they were failing before this lane and were not
  loosened.
- **One refresh opportunity only.** 900 seconds admits a single 600-second
  refresh. A campaign at 3/4 whose universe does not change within that window
  still exhausts — proven here, and intentional minimum scope.
- **A refresh costs budget even when it finds nothing.** The horizon-exhaustion
  scenario still consumed one governed operation from the cumulative 30.
- **Empty aggregator pages are provider failures, not quiet no-ops.** An empty
  GeckoTerminal page classifies as `geckoterminal_no_valid_solana_pools`, so a
  genuinely empty refresh window reports source availability rather than
  duration exhaustion. That is existing adapter behaviour and was not changed;
  operators reading a terminal certificate should not read that classification
  as a market judgement.
- **Cancellation latency is bounded by the refresh interval.** Heartbeat failure
  aborts the wait promptly through the shared failure event; a cooperative
  safe-stop flag written to the database is observed at wake, so worst case is
  the canonical 600 seconds. No polling loop was added to shorten it.
- **The shared work-type slot can legitimately be occupied**, in which case the
  refresh fails closed after its claim. This is safe but forfeits the refresh.
- **Total wall time** can now reach roughly 2,100 seconds (900 acquisition +
  1,200 lifecycle). No source-operation or financial ceiling increased.
- **This is disposable-only evidence.** It proves the mechanism, not live
  provider behaviour, live latency, or real market supply.

## Confirmation of untouched authorities

- **Authoritative database:** never opened, read, written or migrated. Every
  database was a `tempfile` instance, asserted distinct from
  `CANONICAL_PERSISTENT_DB`, which appears in the proof only as an inequality
  operand. `git status -- data/` reports no change. Migration 054 was applied
  **only** to disposable proof databases.
- **Live sources:** zero network access and zero live provider or RPC calls.
  Every governed request in the proof executed through the Source Governor
  against an injected approved fixture transport
  (`geckoterminal_new_pool_discovery`, `pumpswap_pool_account_batch`,
  `pair_market_snapshot`, `restored_pump_migration_signature_page`).
- **Authorization:** none created, consumed, reused or simulated. No manifest,
  no application marker, no wrapper child.
- **Printer live runtime / WINDOW_15M:** not started. No campaign executed, no
  memory generated, no window closed, no retrieval, no decision.
- **Real sleep:** none. Every timed path used an injected fake clock and an
  immediate waiter; the abort boundary was exercised with a pre-set
  `threading.Event`.

## Next lane

`V2-9.8B Post-DTW98 Temporal Persistence Repair Closeout`, then a separate
authoritative migration-054 readiness/application/proof/closeout lane.

Stop here. This lane does not authorize authoritative migration application,
rereadiness, authorization creation, or WINDOW_15M execution.

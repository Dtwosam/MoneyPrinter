# Printer V1 V2-9.8B Terminal Safety and Accounting Finalization Closeout

Date: 2026-07-30

Lane: `V2-9.8B Terminal Safety, Accounting, Runner-Proof, and Supply-Truth Finalization`

Verdict:
`V2_9_8B_TERMINAL_SAFETY_ACCOUNTING_FINALIZATION_PASS`

## Cohesive Sequence Completed

```text
source-grounded re-audit
→ final design
→ complete implementation
→ adversarial frozen proof
→ self-review against the real public path
→ corrected closeout
```

The work was completed as one finalization sequence. It was not split into
micro-lanes and did not stop after the first corrected regression.

## Baseline and Database Invariants

- Branch: `master`
- Start HEAD: `f77237eea4edfa6d79ca3a463979224fbc63b760`
- Start commit: `Repair post-handoff terminal compensation`
- Start HEAD equaled `origin/master`; worktree/index were clean.
- Authoritative DB SHA-256 before:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Authoritative DB SHA-256 after:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head: `049_candidate_acquisition_integration.sql`
- Authoritative DB `PRAGMA integrity_check`: `ok`
- Authoritative DB `PRAGMA foreign_key_check`: zero rows
- No authoritative DB write, migration, live provider/RPC/WebSocket, campaign,
  retry, restart, successor, N2/N7, cursor, recovery, or backfill occurred.

## Money-Usefulness Contribution

Failed ordinary campaigns can no longer erase older same-token learning rows,
silently leave unverifiable residue, cancel another subsystem's lease, or claim
synthetic all-zero accounting. This protects the historical memory corpus and
keeps future money-useful learning honest. Eligible-supply reporting now
distinguishes genuine market shortage from attributable provider failure, so
Printer does not misdiagnose low supply as source unavailability.

## What Was Fixed

### Exact post-handoff ownership

- Added immutable `PostHandoffCompensationScope`.
- The origin owner records the exact origin batch, two token/pair IDs, immutable
  first-15m job IDs, real factory run, real run-step/Scheduler IDs, token
  snapshots, lifecycle events, episode snapshots, and any lease ownership
  (ordinary 15m requires the lease set to be empty).
- All deletions use exact primary keys or the exact origin batch relationship.
  No delete is authorized only by token ID.
- Recorded IDs are verified against factory-run and activated token/pair
  ownership before mutation.
- Duplicate, mixed-owner, wrong-batch, and empty-current-attempt scopes fail
  `POST_HANDOFF_COMPENSATION_SCOPE_MISMATCH` before any subset is deleted.

### Lease isolation

- Removed global `ACTIVE`/`STOPPING` candidate-acquisition lease mutation.
- Ordinary 15m compensation rejects any claimed candidate-acquisition lease
  because this runner creates none.
- Unrelated active leases remain byte-identical and do not count as scoped
  active residue.

### Fail-closed cleanup and verification

- Removed swallowed SQLite errors.
- Added structured `PostHandoffCompensationError` with operation, table,
  campaign/run/cycle, SQLite error category, rollback result, and separately
  preserved first terminal cause.
- The residual matrix verifies exact selection batch/items, run steps,
  lifecycle events, token snapshots, episode snapshots, exact Scheduler jobs,
  immutable-link first-15m jobs, job locks, pinned slots, linked tracking,
  leases, and campaign lifecycle state.
- `clean_zero_active_work` requires complete verification, no cleanup errors,
  preservation equality, and zero scoped active/runnable work.
- Ordered before/after content proves same-token historical rows and unrelated
  state are unchanged.

### Campaign accounting and initialized failure

- `aggregate_campaign_six_unit_owner` rejects missing/empty sequences, `None`
  blocks, empty mappings, malformed evidence, duplicate transport identity,
  negative counters, and owner identity mismatch.
- Added explicit `PRE_OPERATION_NO_WORK` evidence with exact identity and
  deliberate zero-work assertions; implicit empty fallback remains forbidden.
- The public operational coordinator creates the accounting owner before work
  and passes that same owner as a one-way sink to the canonical operational
  owner, so exposed stage evidence is ingested when the stage closes.
- Missing evidence becomes `SIX_UNIT_ACCOUNTING_BLOCKED`; it is never converted
  to an empty stage list.
- A later operational-stage exception marks the owner accounting-blocked while
  preserving already-ingested partial evidence.
- `_terminalize_initialized_failure` requires canonical six-unit evidence for a
  report. Without complete evidence it writes only an accounting-blocked failure
  summary with `report_written=false`, no restart, and no successor.
- Partial evidence remains available in the blocked failure summary and cannot
  overwrite the original terminal cause.

### Real runner proof

- Removed `_apply_and_fault_post_runner`.
- Added a proof-only, disposable-DB fault seam inside
  `run_one_command_15m_factory`; default production behavior is unchanged.
- Real faults occur after committed:
  - first run-step and Scheduler job;
  - first token snapshot;
  - real post-cycle lifecycle event reconciliation;
  - real ordinary 15m terminal step transition.
- The driver catches the real runner fault and invokes the same exact-scope
  compensation owner.

### Eligible-supply truth

- Provider failures are a deterministic set of exact governed facts:
  `(source_name, request_kind, source_failure_id)`.
- A terminal status label no longer adds another provider failure.
- Every distinct DexScreener exact-pair failure counts once and retains Source
  Governor request/failure lineage.
- Valid empty discovery adds zero provider failures.
- True supply, budget, duration, tracking, transport-unavailable,
  rate-limit/stale, and malformed/partial categories remain separate.

## Exact Tables and Owners Affected

| Surface | Canonical owner | Tables verified or mutated |
|---|---|---|
| Post-handoff coordination | `origin_lifecycle_campaign.py` | `printer_selection_batches`, `printer_selection_batch_items`, `printer_memory_factory_run_steps`, `printer_token_lifecycle_events`, `printer_token_snapshots`, `printer_episode_snapshots` |
| Shared terminal authority | `unified_terminal_closure.py::reconcile_campaign_terminal` | campaign/cycle/run state, pinned slots, linked tracking, campaign-owned Scheduler work |
| Real runner | `one_command_15m_factory.py` | real factory run steps, Scheduler jobs, snapshots, lifecycle-event reconciliation |
| Scheduler exact cancellation | Central Scheduler | `printer_scheduler_jobs`; immutable `printer_discovery_selected_item_links` are read-only |
| Lease isolation | candidate-acquisition owner remains separate | `printer_candidate_acquisition_leases` verified only; ordinary compensation performs no lease mutation |
| Campaign accounting | `campaign_six_unit_accounting.py` + public coordinator | durable six-unit evidence and terminal report/summary surfaces |
| Operational stage exposure | `authoritative_live_operational_campaign.py` | one-way evidence callback only; no second ledger or report owner |
| Eligible supply | `eligible_token_supply.py` + Source Governor | `printer_source_requests`, `printer_source_failures`, exhaustion certificate/report surfaces |

No schema table or applied migration was changed.

## Adversarial Runtime Proof

Fresh disposable migration-049 databases and frozen transports were used.

- All six post-handoff fault positions were run through the canonical driver.
- Four final positions were raised inside the real lifecycle runner.
- Every current-attempt ID existed before compensation.
- Older same-token run step, lifecycle event, token snapshot, episode snapshot,
  unrelated selection batch, unrelated Scheduler job, and unrelated active
  acquisition lease were seeded before every fault and remained byte-identical.
- Only exact scoped IDs were deleted or terminalized.
- Mixed valid/invalid scope, other-run ID, wrong batch, duplicate IDs, and empty
  scope after real rows all failed closed with zero unauthorized deletion.
- Injected `sqlite3.OperationalError` at scoped deletion, first-15m
  cancellation, residue verification, and lease verification emitted no clean
  report; rollback status and original cause were retained.
- Actual coordinator accounting boundary covered valid, missing, empty mapping,
  empty sequence, malformed, duplicate, identity mismatch, failure after one
  valid stage, and explicit lawful pre-operation no-work.
- No attempted campaign persisted a matched synthetic-zero report.
- Initialized failure persisted a canonical report only with mandatory matched
  evidence, including a separately proven explicit pre-operation no-work
  terminal; absence and a zero-evidence claim contradicted by durable source
  work remained report-blocked. A failure after one already-ingested stage
  retained partial evidence but remained report-blocked.
- The three prior shared-supply failures are re-enabled and pass:
  24 failures → 24, one failure → one, and valid low-liquidity exhaustion →
  `TRUE_MARKET_SUPPLY_SHORTAGE`.
- A direct ordinary-15m/shared-supply test proves the same one-failure count
  outside a selective-1h wrapper.
- A valid empty finalized Pump signature page adds no failure, while a genuine
  governed Pump transport failure is attributed and counted exactly once.
- Every fault proved zero scoped active work, immutable links retained,
  historical rows retained, unrelated lease retained, integrity/FKs clean,
  idempotent second compensation, and no retry/restart/successor.
- Normal success remains two distinct token/pair slots, two ordinary first-15m
  jobs, immutable links, real runner start, no longer-window/main-5m outcome,
  and no retrieval/financial delta.

## Tests and Checks

- Required combined affected run: **112 passed**.
- Additional active-path restoration regression: **5 passed**.
- Additional authoritative supply-owner callback regression: **8 passed**.
- Total reported lane verification: **125 passed**.
- Python compile checks: PASS.
- `git diff --check`: PASS.
- Static prohibited-pattern checks: PASS.
- Authoritative migration/integrity/FK/hash checks: PASS.

The required combined run includes:

- new terminal-safety/accounting finalization suite;
- existing campaign-accounting suite;
- existing post-handoff compensation suite;
- origin-to-lifecycle integration suite;
- selective-1h liquidity-evidence file as shared-supply regression only;
- broad ordinary one-command 15m suite; and
- initialized-failure lifecycle-integrity suite.

No repository-wide unrelated suite was run.

## Pre-Closeout Adversarial Self-Review

1. Can any DELETE still be authorized only by token ID? **NO** — runtime proof
   in `test_historical_rows_and_unrelated_lease_are_byte_identical` and exact
   mutation review of `_compensate_post_handoff_teardown`.
2. Can one campaign mutate another campaign's lease? **NO** — ordinary
   compensation rejects a non-empty lease scope; proven by
   `test_historical_rows_and_unrelated_lease_are_byte_identical` and
   `test_lease_verification_operational_error_fails_closed`.
3. Can a SQLite error produce `clean_zero_active_work=True`? **NO** — four
   operation-specific runtime injections in
   `test_sql_failures_never_emit_clean_report_and_preserve_unrelated_state` and
   `test_lease_verification_operational_error_fails_closed`.
4. Can an empty stage list produce matched zero evidence? **NO** — actual
   coordinator and aggregator proofs in
   `test_actual_coordinator_accounting_boundary_is_fail_closed` and
   `test_accounting_rejects_absence_malformed_duplicate_mismatch_and_accepts_explicit_no_work`.
5. Can the initialized-failure path persist a lenient canonical report? **NO**
   — `test_initialized_failure_persists_only_mandatory_matched_evidence` and
   `test_post_selection_exception_terminalizes_and_releases_lease` exercise the
   evidence-present and evidence-absent outcomes.
6. Are final fault stages raised inside the real runner? **YES** — four runtime
   checkpoints in `run_one_command_15m_factory`, exercised by
   `test_historical_rows_and_unrelated_lease_are_byte_identical`.
7. Can a valid empty source response count as provider failure? **NO** — shared
   supply regression in the selective-liquidity file plus
   `test_ordinary_15m_shared_supply_counts_one_exact_failure_once`; genuine Pump
   failure attribution is separately covered by
   `test_ordinary_shared_supply_counts_real_direct_pump_failure_once`.
8. Are unrelated historical rows tested, not merely absent? **YES** — seeded,
   ordered, byte-identical comparisons at every fault in
   `test_historical_rows_and_unrelated_lease_are_byte_identical`.
9. Does every PASS claim have runtime proof rather than source-text inspection?
   **YES** — the PASS claims above map to the executed focused and affected
   suites; static inspection is supplementary only.
10. Did any change unlock a prohibited capability? **NO** — zero longer-window,
    retrieval, decision, position, trade, audit, PnL, wallet, or execution delta
    in `test_normal_success_unchanged` and the real-runner fault proofs.

## What Remains Locked

Solana-only; Solana memecoin-only; paper-only; exactly two active tokens;
ordinary `WINDOW_15M` only; support 5m remains support-only; Source Governor and
Central Scheduler; migration 049; no live provider/RPC/WebSocket; no
authoritative DB mutation; no retry/restart/successor; no N2/N7/cursor/recovery/
backfill; no 1h proof or longer-window activation; no retrieval, decisions,
BUY/SELL/HOLD, positions, trades, paper audits, or PnL; no wallet/private key/
signing/real funds/paid API/scoring/ranking/confidence/weighting/embeddings/
vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Exact compensation takes an ordered preservation snapshot of affected
  same-token history and unrelated ownership surfaces. This is intentionally
  heavier than the old token-wide delete but runs only on a terminal fault.
- Tables without campaign columns still rely on the exact IDs captured by the
  runner plus activated token/pair identity; any future writer that bypasses
  the recorder will correctly block compensation.
- `PostHandoffInjectedFault` is private proof-only behavior and is rejected
  outside disposable proof mode. Future runner refactors must preserve the
  checkpoint-after-commit ordering.
- Candidate-acquisition leases remain entirely outside ordinary factory
  authority. If a future approved ordinary runner genuinely acquires one, that
  requires a new ownership design rather than loosening this repair.

## Exact Remaining Unproven Items

None inside the requested frozen/disposable finalization boundary.

Live providers, live RPC/WebSockets, an authoritative Memory Factory campaign,
N2/N7, recovery/cursors/backfill, selective 1h operation/proof, longer windows,
retrieval, and every financial capability remain intentionally unproven and
unauthorized; they are locks, not discrepancies in this PASS.

## Exact Next Permitted Task

Independent read-only operator review of this branch, diff, audit, design,
tests, and closeout only.

This PASS does not authorize a live probe or Memory Factory campaign.

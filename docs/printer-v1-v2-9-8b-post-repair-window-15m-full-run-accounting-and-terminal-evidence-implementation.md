# Printer V1 V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Implementation

Date: 2026-07-31

Lane:
`V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Implementation`

Branch:
`codex/v2-9-8b-full-run-accounting-terminal-evidence-implementation`

Baseline:
`463a80e30b26af2824d370e1ca5dcd2028c9d01e`

Type: implementation + focused disposable-DB tests only. No live campaign,
preflight, report-only against the authoritative DB, discovery, N2/N7, cursor,
provider, RPC, or WebSocket path was run. The authoritative database was not
opened or mutated. No historical row, artifact, or no-rerun marker was edited.

Verdict:
`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_PASS`

## 1. Scope

Implements the approved design
(`docs/printer-v1-v2-9-8b-post-repair-authoritative-window-15m-full-run-accounting-and-terminal-evidence-design.md`)
slices 1–6 as testable, composable primitives that reuse the existing ownership,
accounting, and reconciliation owners. No parallel ownership table, second
Scheduler, second source authority, or competing terminal report was created.
The primitives are proven on disposable databases; wiring them into the live
operational coordinator is deferred to the bounded-proof lane, which is the only
place a live attempt could occur.

## 2. Files changed

| File | Change |
| --- | --- |
| `src/printer_v1/sources/measured_transport.py` | Added three frozen non-transport identity dataclasses (`SchedulerWorkIdentity`, `LifecycleReservationIdentity`, `LocalValidationIdentity`) with stable identity keys. Purely additive. |
| `src/printer_v1/sources/campaign_six_unit_accounting.py` | Extended `CampaignSixUnitOwner` with identity ledgers for the three non-transport units and V2 durable evidence; extended `seal_campaign_stage_evidence` / `ingest_stage_evidence` / `reconstruct_six_unit_totals_from_evidence` to carry and validate identity lists (`CAMPAIGN_SIX_UNIT_EVIDENCE_V2`); added `CampaignActionLocalLedger`; added `reconcile_full_run_owner_to_action_local`; made `reconcile_owner_to_action_local` non-vacuous for lifecycle-started runs. Backward compatible: V1 behaviour is byte-identical when no identity/lifecycle argument is supplied. |
| `src/printer_v1/operator_cli/campaign_ownership.py` | Added `register_campaign_window_close` (atomic cycle-id set + campaign-window ownership + memory-row bind + terminalize + read-back, idempotent, fail-closed) and `project_campaign_scheduler_job` (project existing Scheduler job ids, one-job-one-row, idempotent). Purely additive; existing helpers untouched. |
| `src/printer_v1/operator_cli/campaign_full_run_accounting.py` | New module: `OperationalLifecycleOwnershipContext` (identity flow + factory-run drift), `resolve_campaign_slot_terminal_disposition`, `evaluate_quality_consistency`, `build_full_run_terminal_report`, `evaluate_campaign_acceptance_gate`. |
| `tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py` | New focused disposable-DB test module (17 tests). |
| `docs/printer-v1-v2-9-8b-post-repair-window-15m-full-run-accounting-and-terminal-evidence-implementation.md` | This report. |

## 3. Exact ownership and accounting flow implemented

1. **Exact lifecycle ownership (item 1).** `register_campaign_window_close` runs
   as one atomic transaction. It verifies the succeeded `WINDOW_CLOSE` step
   belongs to the immutable ownership context (factory run, token/pair, memory
   row), verifies the campaign run is bound to that factory run, sets
   `printer_memory_windows.cycle_id` to the exact `cycle_id`, inserts the
   `printer_memory_factory_campaign_windows` ownership row bound to the exact
   token slot / token / pair / lifecycle identity, terminalizes it to the closed
   state, and read-back verifies before returning. Exact-repeat registration is
   idempotent; a competing campaign/run/cycle owner, token/pair mismatch, blank
   or mismatched cycle in a new run, or an out-of-context close step fails closed
   with `CAMPAIGN_WINDOW_OWNERSHIP_CONFLICT`. The existing ownership helpers and
   table are reused; no parallel window map exists.
2. **Scheduler ownership (item 2).** `project_campaign_scheduler_job` projects an
   existing Scheduler job id (factory snapshot and `WINDOW_CLOSE` jobs) into
   `printer_memory_factory_campaign_scheduler_work`, referencing the canonical
   `printer_scheduler_jobs` id and the factory run-step linkage. The
   `scheduler_work_id` is a deterministic function of campaign + job so one job
   maps to exactly one ownership row; a second projection under a different
   owner/window fails closed. Campaign, run, cycle, factory run (via the campaign
   run→factory run bind and the run-step link), token slot, campaign window,
   factory step (via `run_steps.scheduler_job_id`), job kind (in `work_intent`),
   Scheduler job, and terminal status are all persisted or provable.
3. **Full-run six-unit accounting (item 3).** The three non-transport units now
   have durable identity records. `CampaignSixUnitOwner` records
   Scheduler-work / lifecycle-reservation / local-validation identities, derives
   the three totals from unique identity sets, and emits
   `CAMPAIGN_SIX_UNIT_EVIDENCE_V2` durable evidence. Historical V1 evidence stays
   readable and replayable; no historical report is rewritten.
4. **Independent action-local evidence (item 4).** `CampaignActionLocalLedger`
   observes transport, Scheduler, reservation, and validation operations at their
   execution boundaries, separately from sealed owner evidence. Final equality
   compares exact identity sets and counts in both directions for every unit.
5. **Non-vacuous reconciliation (item 5).** `reconcile_owner_to_action_local`
   fails closed when a lifecycle-started run lacks a required action-local
   surface (`ACTION_LOCAL_LIFECYCLE_EVIDENCE_MISSING`), on count mismatch,
   identity mismatch, duplicate identity, or a missing mandatory sealed stage
   (`MISSING_MANDATORY_LIFECYCLE_STAGE`). It never returns `equal=True` merely
   because both optional arguments are absent.
6. **Terminal reporting and PASS gate (item 6).** `build_full_run_terminal_report`
   exposes selected token/pair identities, factory run id, exact campaign-window
   and memory-window ids, coverage/window/quality labels, per-token terminal
   outcome, exact Scheduler ownership + attribution, the full lifecycle stage
   manifest, owner/action-local reconciliation, zero active residue, and
   forbidden-capability deltas, keeping runtime terminal status, campaign
   acceptance, and memory quality as three distinct axes.
   `evaluate_campaign_acceptance_gate` makes PASS impossible unless exactly two
   distinct terminal `WINDOW_15M` lifecycles occurred, both are campaign-owned,
   full-run stage evidence is complete, owner/action-local equality is
   non-vacuously proven, canonical reporting is complete, and cleanup/locks are
   safe.
7. **Terminal semantics (item 7).** `resolve_campaign_slot_terminal_disposition`
   maps a completed owned lifecycle whose queue disposition is `COOLDOWN` to slot
   `COOLDOWN`, never relabelling it `MANUAL_REVIEW`; a still-`SELECTED` slot with
   no lifecycle may become `MANUAL_REVIEW`; the tracking queue keeps its own
   status.
8. **Quality consistency (item 8).** `evaluate_quality_consistency` blocks a
   `WINDOW_15M_CLEAN_MEMORY` episode for any `PARTIAL_MEMORY` / dirty /
   `DO_NOT_TRAIN` window while leaving lifecycle completion valid. Historical
   windows `161`/`162` and episodes `58`/`59` are untouched; no backfill or
   reclassification occurs.

## 4. Schema decision

**No migration was added.** Static inspection of `migrations/032_campaign_ownership_schema.sql`,
`migrations/021_repeatable_evidence_windows.sql`, and `migrations/028_memory_factory_run_ledger.sql`
confirms the existing schema can enforce one exact ownership row per canonical id:

- `printer_memory_factory_campaign_windows.window_id` is the primary key →
  campaign-window registration is idempotent by primary key.
- `printer_memory_factory_campaign_scheduler_work.scheduler_work_id` is the
  primary key, and `scheduler_job_id` references `printer_scheduler_jobs(id)` →
  the deterministic `scheduler_work_id` and an explicit one-job-one-row check
  enforce a single ownership row per Scheduler job.
- `printer_memory_windows.cycle_id` exists (migration 021) and is mutable → the
  exact campaign cycle id can be bound in the close transaction.
- Factory run, factory step, and job kind are provable through existing linkage
  (`printer_memory_factory_campaign_runs.authoritative_run_id`,
  `printer_memory_factory_run_steps.scheduler_job_id`) and `work_intent`; no new
  columns are required.
- V2 six-unit evidence and the full-run report are JSON payloads → no schema
  change.

No missing invariant was found that could not be enforced through an existing
primary key, so implementation did not stop for a design amendment and did not
add an opportunistic migration.

## 5. Focused tests and outputs

New module `tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py` (disposable
temp databases only; never points at `data/printer_v1.sqlite3`):

```
PYTHONPATH=src python -m pytest tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py -q
17 passed in 2.13s
```

Coverage against the required proofs:

1. two-token completion creates exactly two campaign-owned windows — `test_two_token_completion_creates_two_campaign_owned_windows`;
2. both memory windows carry the exact cycle identity — `test_both_memory_windows_carry_exact_cycle_identity`;
3. all existing factory Scheduler jobs have exact campaign ownership (18 jobs, one row each, no duplicate jobs) — `test_all_factory_scheduler_jobs_have_exact_campaign_ownership`;
4. full-run identity-bearing six-unit evidence reconstructs exact totals — `test_full_run_evidence_reconstructs_exact_totals`;
5. independent action-local equality succeeds on exact evidence — `test_independent_action_local_equality_succeeds`;
6. missing action-local lifecycle evidence fails closed — `test_missing_action_local_lifecycle_evidence_fails_closed`;
7. count, identity, duplicate, missing-stage, window-ownership, and Scheduler-ownership conflicts fail closed — `test_count_identity_duplicate_and_stage_conflicts_fail_closed`, `test_ownership_conflict_fails_closed`, `test_close_step_outside_factory_run_fails_closed`, `test_scheduler_projection_is_idempotent_and_conflict_fails_closed`;
8. completed owned lifecycle does not become `MANUAL_REVIEW` — `test_completed_owned_lifecycle_does_not_become_manual_review`;
9. partial/dirty window cannot create a clean episode — `test_partial_or_dirty_window_cannot_create_clean_episode`;
10. canonical terminal report includes both exact token/window outcomes and gate PASS — `test_canonical_report_includes_both_exact_token_window_outcomes`;
11. report-only replay is exact-identity, zero-source, zero-Scheduler, zero-write — `test_report_only_replay_is_exact_identity_zero_side_effect`;
12. retrieval and all financial deltas remain zero — `test_retrieval_and_financial_deltas_remain_zero`;
plus idempotent registration and a `BLOCKED_UNSAFE` gate proof for a partially-owned run.

Directly-affected existing modules re-run green (no regression from the shared-module edits):

```
PYTHONPATH=src python -m pytest \
  tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py \
  tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py \
  tests/test_v2_9_7d_6b_6_final_campaign_report.py \
  tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py \
  tests/test_v2_9_8b_terminal_safety_accounting_finalization.py \
  tests/test_v2_9_7e_46b_2_source_accounting.py \
  tests/test_post_rc_lane_e2c_b_source_budget_accounting.py -q
124 passed, 3 subtests passed
```

## 6. Backward compatibility

- `measured_transport.py` and `campaign_ownership.py` changes are strictly
  additive; no existing symbol or behaviour changed.
- `campaign_six_unit_accounting.py` stays byte-compatible for V1 callers: the
  owner emits V1 evidence unless a non-transport identity was recorded;
  `reconcile_owner_to_action_local` keeps its prior transport-only path when
  `lifecycle_started` is false and no `action_local_ledger` is supplied; V2 is an
  additive evidence kind.
- Historical V1 evidence remains readable and replayable and is never upgraded to
  V2 PASS evidence.

## 7. Failure and rollback behaviour

- Window-close registration is one atomic transaction; if ownership cannot be
  registered and read-back verified, it raises and the transaction rolls back —
  no unowned committed future window is accepted.
- Any malformed, missing, duplicate, unsealed, or mismatched stage blocks report
  acceptance; the first terminal cause is preserved and no operation identity is
  fabricated from row counts.
- Repeated registration / projection over the same terminal graph is idempotent:
  no new ownership rows, no duplicate stage evidence, same projection returned.
- Replay reconstructs from durable rows/evidence only, performs no source call,
  Scheduler action, or write, and cannot select a report by fallback.

## 8. Money-usefulness contribution

Defensive money-usefulness only. The campaign can now prove *who owned* each real
factory window, *which operations* created it, whether owner and independent
action-local evidence *reconcile exactly*, and what the *actual terminal quality*
was — before any window could ever be treated as a clean learning episode. It
prevents false PASS terminals from entering operational history, makes two-token
learning runs auditable by exact identity, and keeps partial/dirty outcomes from
being promoted as clean, while retrieval and every financial capability stay
locked. It makes no profit claim and creates no trading capability.

## 9. What this implementation improves

- Closes the factory-to-campaign window ownership gap and the campaign Scheduler
  ownership gap with exact, idempotent, fail-closed registration.
- Extends six-unit accounting through the real lifecycle with identity-bearing
  non-transport units.
- Replaces vacuous reconciliation with exact non-empty bidirectional equality.
- Makes the terminal report show the real two-token/window outcomes and separates
  runtime completion, campaign acceptance, and memory quality.
- Preserves valid `COOLDOWN` semantics and prevents clean episode labels from
  contradicting non-clean windows.

## 10. What remains locked

Implementation of the live wiring, a live campaign or rerun, clean-memory
promotion of historical windows `161`/`162`, `WINDOW_1H`/`4H`/`12H`/`24H`,
retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
wallets, private keys, signing, real funds, paid APIs, and scoring/ranking/
confidence/weighting/embeddings/vectors all remain locked.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Why it matters | Mitigation in this lane | Proof still required |
| --- | --- | --- | --- |
| Live close path may commit before ownership registration | Could create a real but campaign-orphaned window | `register_campaign_window_close` is atomic and read-back verified; a non-atomic underlying close owner would need an explicit compensation boundary | Fault injection at every live close/registration boundary in the bounded-proof lane |
| Primitives are not yet wired into the operational coordinator | Design intent unproven end-to-end in the live path | Slices delivered as composable, individually-proven units on disposable DBs | One bounded disposable end-to-end proof driving coordinator → factory → report |
| Scheduler ownership table requires a non-null campaign `window_id` | Discovery/selection jobs have no window | Window-scoped lifecycle jobs (snapshot + close) are projected into the table; discovery/selection Scheduler ownership is carried by the `DISCOVERY_SELECTION_SCHEDULER` six-unit stage | Confirm the live discovery/selection stage seals its Scheduler identities in the bounded-proof lane |
| Two pre-existing baseline test failures | Could be mistaken for regressions | Confirmed identical with changes stashed: `test_v2_9_7e_44_full_pilot_supply_integration.py::WiringTests::test_closed_supply_stage_flows_to_top_accounting_owner` and both git-provenance-field failures in `test_v2_9_3_early_failure_accounting_repair.py` fail at baseline `463a80e` | None from this lane; recorded, not expanded into scope |

## Proof still required before completion

1. Bounded disposable end-to-end proof driving the live coordinator → factory →
   registration → projection → report → gate, with the required negative proofs
   from design §17.2.
2. Fault-injection proof that a live non-atomic close either registers atomically
   or terminalizes `BLOCKED_UNSAFE`.
3. Confirmation that the live discovery/selection stage seals its Scheduler and
   validation identities so the action-local equality holds operationally.

## Verdict

`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_PASS`

A PASS here means implementation and focused disposable tests pass. It does not
authorize a live campaign.

## Exact next permitted lane

```text
V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Bounded Proof
```

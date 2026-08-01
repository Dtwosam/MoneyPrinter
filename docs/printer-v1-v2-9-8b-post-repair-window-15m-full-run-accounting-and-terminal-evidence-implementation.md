# Printer V1 V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Implementation

> **Wiring Correction Addendum (2026-07-31).** The original commit `0f6f7a9`
> implemented and tested the primitives but did **not** wire them into the
> ordinary coordinator/factory path — see
> [§C. Wiring Correction](#c-wiring-correction) for the correction, the exact
> runtime wiring added, the transaction/compensation boundary, and the new
> integration tests that drive the real factory to two closes.

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
| ~~Primitives are not yet wired into the operational coordinator~~ **(RESOLVED in §C)** | Design intent was unproven end-to-end in the live path | Now wired: coordinator threads the operation observer + ownership context through owner → driver → factory and invokes `finalize_full_run_ownership_and_report`; proven by real-factory integration tests | Bounded-proof lane still exercises the full live command against a disposable operational DB |
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

---

## C. Wiring Correction

Date: 2026-07-31. Commit: `Wire full-run 15m accounting into operational coordinator`.

### C.1 Why `0f6f7a9` was incomplete

Commit `0f6f7a9` delivered and unit-proved the primitives
(`register_campaign_window_close`, `project_campaign_scheduler_job`,
identity-bearing six-unit evidence, `CampaignActionLocalLedger`, non-vacuous
`reconcile_owner_to_action_local`, the full-run report and acceptance gate), but
**nothing in the ordinary operational coordinator/factory path called them**. The
factory still closed memory windows without producing campaign-window ownership,
Scheduler ownership, lifecycle six-unit stages, or an acceptance verdict — exactly
the disconnect the forensic closeout found. A bounded-proof lane would therefore
have had nothing implemented to prove. This addendum wires the primitives into
the real path.

### C.2 Exact runtime wiring added

Runtime path now flowing:
`operational command → AuthoritativeLiveOperationalCampaignOwner.run_operational →
OriginToLifecycleCampaignDriver.run → run_one_command_15m_factory → close/terminal
→ full-run finalization → canonical terminal summary`.

Files changed in the correction:

| File | Wiring |
| --- | --- |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | Added additive `lifecycle_ownership_context` (factory-run **drift check**: a non-empty bound factory-run id that disagrees with the factory's own run id fails closed before any lifecycle work) and `lifecycle_operation_observer` (fired at the real Scheduler-enqueue boundary in `_insert_step_and_job`, threaded through `_plan_opening_jobs`/`_plan_anchored_jobs`). Default `None`, so non-wired callers are byte-unchanged. |
| `src/printer_v1/operator_cli/campaign_full_run_accounting.py` | Added shared `lifecycle_step_identities` (used by **both** the action-local observer and the owner sealing so keys match only when the same operation was executed *and* owned), `build_lifecycle_action_local_observer`, and `finalize_full_run_ownership_and_report` — the campaign-layer boundary that registers windows, projects jobs, seals owner lifecycle stages from committed rows, reconciles against the execution-time ledger, builds the report, and gates PASS. |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | The coordinator threads `lifecycle_ownership_context` + `lifecycle_operation_observer` into `lifecycle_kwargs` (propagated unchanged through the owner and driver to the factory), collects the execution-time operation records, and after the factory returns invokes `_apply_full_run_campaign_acceptance` → `finalize_full_run_ownership_and_report`. The canonical terminal summary now carries `campaign_acceptance_verdict`, `campaign_pass`, and `full_run_campaign_acceptance`, kept **separate** from `run_status` (runtime terminal). |

Independent action-local evidence is genuinely captured at execution time: the
factory reports each Scheduler enqueue as it happens; the coordinator mints
identities from those records **after** the factory-run id is known and stores
them in a `CampaignActionLocalLedger`. The owner side is sealed **separately** by
`finalize` reading the committed `run_steps`. The two derivations are equal only
when every executed operation was also owned — a real cross-check, not a
self-comparison or a report-derived copy.

### C.3 Transaction / compensation boundary

The underlying memory-window close commits inside the factory before campaign
ownership can be registered, so this is **not** one atomic transaction across
close-and-register, and the report does not claim it is. `finalize` is the
approved explicit **fail-closed compensation boundary**:

- each `register_campaign_window_close` is itself atomic (cycle-id set +
  ownership insert + memory-row bind + terminalize + read-back, rolled back on
  any fault) and idempotent;
- a registration or projection fault is preserved in `blocked_reasons` and forces
  `BLOCKED_UNSAFE`;
- with fewer than two owned terminal windows, or a non-empty block list, or a
  reconciliation mismatch, the acceptance gate cannot return PASS;
- runtime `COMPLETED` is never promoted to Campaign PASS.

### C.4 Focused test results

```
PYTHONPATH=src python -m pytest \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_terminal_evidence.py -q
25 passed
```

`tests/test_v2_9_8b_full_run_wiring_integration.py` (8 tests) drives the **real**
`run_one_command_15m_factory` with injected adapters to two real terminal
`WINDOW_15M` closes on a disposable DB, then the **real** finalize / coordinator
helper. It proves: (1) the real factory completes two closes and fires the
observer for both tokens; (2) finalize registers two exact campaign-owned windows;
(3) it projects every lifecycle Scheduler job one-row-each; (4) action-local
identities are captured independently during execution; (5) owner slot stages are
sealed and ingested; (6) owner/action-local equality is non-vacuous; (7) the
canonical report is produced and the gate returns `CAMPAIGN_PASS`; (8) PASS is
blocked when action-local evidence is missing or a single enqueue identity is
removed; (9) COOLDOWN + quality consistency are preserved; (10) retrieval and
financial deltas stay zero; plus factory-run drift fails closed and the coordinator
helper (`_apply_full_run_campaign_acceptance`) gates PASS / HONEST_BLOCKED.

Regression (directly affected suites, all green):

```
tests/test_v2_4_one_command_15m_factory.py
tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py
tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py
tests/test_v2_9_8a_public_operational_command.py
tests/test_v2_9_7d_6b_1_campaign_ownership_schema.py
tests/test_v2_9_8b_accounting_exact_identity_report_only_repair.py
tests/test_v2_9_7d_6b_6_final_campaign_report.py
tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py
tests/test_v2_9_8b_terminal_safety_accounting_finalization.py         → 169 passed
tests/test_v2_9_8b_post_handoff_terminal_compensation.py
tests/test_v2_9_7e_9_two_token_continuous_lifecycle.py
tests/test_v2_9_8b_18_heartbeat_terminalization_repair.py             →  26 passed
tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py
tests/test_v2_5_multi_token_15m_conservative.py                       →  53 passed
```

Pre-existing baseline failures (unchanged, recorded not fixed):
`test_v2_9_7e_44_full_pilot_supply_integration.py::WiringTests::test_closed_supply_stage_flows_to_top_accounting_owner`
and the two git-provenance-field failures in
`test_v2_9_3_early_failure_accounting_repair.py` — all fail at baseline `463a80e`
with the branch changes stashed.

### C.5 Confirmation the ordinary runtime path now consumes the primitives

The public coordinator `_run_operational_campaign` now (a) propagates the ownership
context and operation observer to the factory, (b) captures execution-time
operation records, and (c) invokes `_apply_full_run_campaign_acceptance` after the
factory returns, folding `campaign_acceptance_verdict` / `campaign_pass` /
`full_run_campaign_acceptance` into the canonical terminal summary. The
integration test drives the exact same helper the coordinator calls, on real
committed factory rows, and proves it registers ownership and gates PASS. No
operational command was run and the authoritative database was neither opened nor
mutated in this lane.

### C.6 Remaining proof requirements

1. The bounded-proof lane runs the full public command against a **disposable**
   operational DB end to end (the integration tests here drive the factory +
   finalize directly and the coordinator helper, not the outer supervision /
   backup / heartbeat shell).
2. Fault-injection at the live close/registration boundary confirming a
   registration failure terminalizes `BLOCKED_UNSAFE`.
3. The design's negative proofs from §17.2 exercised through the wired path.

### C.7 Money-usefulness, locks, risks (correction delta)

Money-usefulness is unchanged and now *actually enforced on the ordinary path*: a
real two-token learning run cannot be accepted as PASS unless the campaign proves
exact ownership, exact Scheduler attribution, non-vacuous owner/action-local
equality, and a complete canonical report — otherwise it is `BLOCKED_UNSAFE`. All
locks in §10 remain: `WINDOW_15M` only, retrieval / paper decisions / BUY-SELL-HOLD
/ positions / trades / audits / PnL / wallets / keys / paid APIs / scoring locked;
support-only 5m stays non-authoritative; no historical row or report was rewritten;
**no migration** was added.

**Functionality Risks / Setbacks / Efficiency Blockers (correction):**

| Risk / blocker | Why it matters | Mitigation | Proof still required |
| --- | --- | --- | --- |
| Close commits before ownership registration (not one atomic transaction) | A crash between close and register could leave a real orphan window | `finalize` is an explicit fail-closed compensation boundary; each registration is atomic + idempotent; unregistered ⇒ fewer than two owned windows ⇒ no PASS | Live fault-injection between close and register in the bounded-proof lane |
| Action-local observer covers the Scheduler-enqueue boundary (scheduler/reservation/validation), transports via the existing measurement observer | If a future unit executed outside these boundaries it would escape independent capture | Owner and action-local are sealed from different sources and must be identical; any divergence blocks PASS | Extend/observe additional execution boundaries if new lifecycle units appear |
| Factory instrumentation touches core planning functions | Regression risk across the lifecycle suite | Additive `None`-default params only; full lifecycle + factory suites re-run green | Bounded-proof lane end-to-end run |
| Integration tests drive factory + finalize + coordinator helper, not the full supervision shell | The outer backup/heartbeat/lease shell is not exercised here | That shell is unchanged and separately tested; wiring is proven at the coordinator-helper seam | Full disposable end-to-end command in the bounded-proof lane |

### C.8 Correction verdict

`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_PASS`

The real coordinator/factory path is wired and focused disposable integration
tests pass. This does not authorize a live campaign. Next permitted lane remains
`V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Bounded Proof`.

---

## D. Second correction — evidence-semantics repair

The first correction wired the primitives into the coordinator/factory path but
the sealed evidence was still *semantically hollow*: owner slot stages were sealed
with empty transport evidence; reservation and validation identities were minted
one-per-Scheduler-job; `pair_id` was derived from `token_id`; the gate consumed
hardcoded `authorized_invocation_count=1`, `runtime_terminal_status=
"TERMINAL_COMPLETED"`, and a default-true lease; Scheduler ownership was projected
as a hardcoded `SUCCEEDED`; quality always passed `proposed_episode_kind=None`; and
a compensation block could leave an embedded gate still reading `CAMPAIGN_PASS`.
This correction replaces every one of those with a value measured from durable
rows or observed at the real execution boundary.

### D.1 Exact evidence semantics

* **Owner is sealed from durable rows; action-local is observed at execution.**
  The two derivations remain independent and must be identical or PASS is blocked.
* **Equality is scoped to what an observer can witness.** `reconcile_full_run_owner_
  to_action_local` gained an additive `owner_equality_stage_ids` filter. The
  owner↔action-local six-unit equality is proven over the two lifecycle **slot**
  stages (the transports, reservations, validations and Scheduler work the factory
  actually observed). The two owner-only mandatory stages
  (`DISCOVERY_SELECTION_SCHEDULER`, `CAMPAIGN_TERMINAL_RECONCILIATION`) stay
  required-present but are excluded from equality — neither vacuous nor forced to
  invent observations. Omitting the filter preserves the original all-stages
  contract, so every prior accounting test is unchanged.
* **Fail-closed transport proof.** A lifecycle-started run whose lifecycle steps
  issued source requests can never seal zero source transport identities
  (`LIFECYCLE_SOURCE_TRANSPORT_IDENTITIES_ZERO`).

### D.2 Actual transport / reservation / validation boundaries

Three genuinely distinct boundaries, no longer collapsed onto the enqueue event:

| Unit | Boundary | Real quantity |
| --- | --- | --- |
| `SCHEDULER_WORK_ITEM` | `SCHEDULER_ENQUEUE` (plan time) | exactly one per enqueued run-step job |
| `LIFECYCLE_RESERVED_TRANSPORT_OPERATION` | `SCHEDULER_ENQUEUE` | the step's **projected governed operations**: `SNAPSHOT` → 1, `WINDOW_CLOSE` → `1 + PRECLOSE_CONTEXT_REQUEST_COUNT` (= 6). A close reserving many calls is **never** collapsed to one reservation because it is one Scheduler job. |
| `SOURCE_TRANSPORT_OPERATION` + `LOCAL_VALIDATION_STEP` | `SOURCE_TRANSPORT` (the actual measured outbound-call boundary the factory now fires) | one measured source transport (keyed on the durable `source_request_id`, carrying real response bytes / normalized rows) and one exact-pair verification validation per observation that actually produced a response |

Real measured example (two `TRACK_NORMAL` tokens, 8 snapshots each + close, driven
through the real factory): `SOURCE_TRANSPORT_OPERATION=18`,
`SOURCE_RESPONSE_BYTES=7398`, `NORMALIZED_SOURCE_ROWS=18`, `SCHEDULER_WORK_ITEM=18`,
`LIFECYCLE_RESERVED_TRANSPORT_OPERATION=28` (16×1 + 2×6). Reservation ≠ Scheduler
work ≠ transport — the three axes are independent and exact. A
`PRECLOSE_CONTEXT_REQUEST_COUNT` guard test asserts it stays equal to the factory's
`_CONTEXT_REQUESTS_PER_TOKEN`, so the projected reservation cannot silently drift.

### D.3 Exact token and pair identity

`finalize` carries the real `token_id`/`token_mint`, `pair_id`/`pair_address`,
`tracking_lane`, memory-window id and campaign-window id from the `WINDOW_CLOSE`
step and its campaign slot. `pair_id` is the step's own column — never derived from
`token_id`. Tests seed deliberately different values (token `1`→pair `101`, token
`2`→pair `102`) and assert the report reflects the exact distinct identities.

### D.4 Exact terminal and authorization gate inputs

`finalize_full_run_ownership_and_report` now **requires** the durable facts —
`authorized_invocation_count`, `runtime_terminal_status`, `lease_released` — and
also carries `runtime_first_terminal_cause` and `active_work_result`. The hardcoded
`authorized_invocation_count=1`, `runtime_terminal_status="TERMINAL_COMPLETED"`, and
`lease_released: bool = True` default are gone. The coordinator derives
`authorized_invocation_count` from the count of factory runs authoritatively bound
to the campaign run, `runtime_terminal_status` from the factory run row, and threads
`lease_released` / `active_work_result` from `cleanup_campaign_supervision`
(unified terminal cleanup), which runs before campaign acceptance is evaluated. New
gate checks: `exactly_one_authorized_invocation`, `runtime_terminal_completed`,
`lease_released`, `memory_quality_consistent`,
`scheduler_ownership_correspondence_exact`,
`all_lifecycle_scheduler_jobs_succeeded`, and `all_mandatory_stages_sealed`.

### D.5 Complete mandatory stages and accurate Scheduler ownership

All four approved stages are sealed and required; removing any one drops
`all_mandatory_stages_sealed` and blocks PASS. Scheduler ownership reads each job's
real `printer_scheduler_jobs.status` (mapped `SUCCEEDED/FAILED/CANCELLED/SKIPPED`);
a non-terminal job is `SCHEDULER_JOB_NOT_TERMINAL` and blocks. The report carries
`scheduler_ownership` with exact per-job states, missing/extra ownership, and the
`correspondence_exact` verdict; a `FAILED`/`CANCELLED` lifecycle job is visible and
blocks PASS.

### D.6 Quality consistency and report/verdict agreement

`finalize` inspects the real `printer_episodes` attached to each exact memory
window and passes the real `proposed_episode_kind`. A partial/dirty/`DO_NOT_TRAIN`
window carrying a `WINDOW_15M_CLEAN_MEMORY` episode yields
`QUALITY_CONSISTENCY_BLOCKED` and blocks PASS (lifecycle completion of the window
itself stays valid). The canonical report, embedded gate object and top-level
verdict are reconciled to a single value: a compensation block downgrades every
surface together, so no embedded gate can read `CAMPAIGN_PASS` while the run is
blocked.

### D.7 Tests and outputs

New focused suite
`tests/test_v2_9_8b_full_run_accounting_semantics_correction.py` (disposable DBs,
injected transports only) proves all twelve required properties:

1. lifecycle source transports/bytes/rows nonzero and exact;
2. removing one measured transport identity blocks;
3. reservation totals reflect per-step projected reservations (close ≠ one);
4. validation identities arise only from executed observations;
5. token id differs from pair id and stays exact;
6. authorization count 0 or 2 blocks;
7. unreleased lease blocks;
8. non-completed runtime status is not masked and blocks;
9. each of the four mandatory stages is independently required;
10. failed/non-terminal Scheduler state is reported accurately and blocks;
11. a partial window with a clean episode blocks;
12. report, gate and top-level verdict cannot disagree
    (plus a projected-reservation drift guard).

```
tests/test_v2_9_8b_full_run_accounting_semantics_correction.py  → 14 passed, 6 subtests
```

Re-run of the focused primitive / wiring / coordinator / factory / ownership /
accounting / terminal suites:

```
test_v2_9_8b_full_run_accounting_semantics_correction.py
test_v2_9_8b_full_run_accounting_terminal_evidence.py
test_v2_9_8b_full_run_wiring_integration.py
test_v2_9_8b_accounting_exact_identity_report_only_repair.py
test_v2_9_8b_campaign_accounting_terminal_enforcement.py
test_v2_9_8b_terminal_safety_accounting_finalization.py
test_v2_9_7d_6b_1_campaign_ownership_schema.py
test_v2_4_one_command_15m_factory.py
test_v2_9_7e_11_authoritative_live_operational_campaign.py
test_v2_9_8b_post_handoff_terminal_compensation.py
                                                → 193 passed, 6 subtests in ~70s
```

The real factory run now yields non-vacuous exact totals (§D.2), all four stages
sealed, `correspondence_exact=True`, `all_lifecycle_jobs_succeeded=True`, scoped
equality over the two slot stages, and agreeing report/gate/verdict all reading
`CAMPAIGN_PASS`.

### D.8 Money-usefulness contribution

A two-token 15m learning run is only accepted as `CAMPAIGN_PASS` when the campaign
proves it actually *did the measured work*: real source transports with real bytes,
per-step reserved capacity, executed validations, exact distinct token/pair
identity, every Scheduler job owned once in its real terminal state, all four
mandatory stages sealed, a released lease, exactly one authorization, a completed
runtime, and consistent memory quality. Hollow or forged evidence can no longer
buy a PASS — the accounting is now worth trusting for downstream learning value.

### D.9 What remains locked

All §10 locks hold unchanged: `WINDOW_15M` only; retrieval / paper decisions /
BUY-SELL-HOLD / positions / trades / audits / PnL / wallets / keys / paid APIs /
scoring locked; support-only 5m non-authoritative; no operational command, live
campaign, provider, RPC, WebSocket, preflight, recovery, discovery-only, N2/N7 or
cursor execution was run; `data/printer_v1.sqlite3` was neither opened nor mutated;
**no migration** was added; no historical execution row, artifact or marker was
edited. The bounded-proof lane remains locked pending operator review of this
correction.

### D.10 Functionality Risks / Setbacks / Efficiency Blockers (second correction)

| Risk / blocker | Why it matters | Mitigation | Proof still required |
| --- | --- | --- | --- |
| Owner↔action-local equality is scoped to the two lifecycle slot stages | The discovery and terminal stages are proven present but not by execution-time equality | They are sealed only from durable ownership/terminal facts and are independently required; the lifecycle equality (transports, reservations, validations, Scheduler work) is exact and non-vacuous | Observe discovery-selection and terminal reconciliation at their own execution boundaries in the bounded-proof lane |
| Projected `WINDOW_CLOSE` reservation (`1 + PRECLOSE_CONTEXT_REQUEST_COUNT`) is a constant mirror of the factory | Drift would misstate reservations | A guard test asserts equality with `_CONTEXT_REQUESTS_PER_TOKEN`; both derivations use the same pure map so they cannot diverge from each other | Fold the factory constant into a single shared source in a later lane |
| Lifecycle source transport = the exact-pair snapshot call linked to each step; the pre-close context bundle is not counted as lifecycle transport | Context-bundle calls are readiness/safety, not the 15m observation | Reservation still projects the full close capacity (6); transport counts only the exact-pair observation, keyed on the durable `source_request_id` | Confirm the intended scope of "lifecycle transport" at operator review |
| `finalize` remains a post-cleanup compensation boundary (close commits before ownership registration) | A crash between close and register could orphan a window | Each registration is atomic + idempotent; fewer than two owned windows ⇒ no PASS; any fault ⇒ `BLOCKED_UNSAFE` | Live fault-injection between close and register in the bounded-proof lane |
| Factory now fires a second observation at the source-transport boundary | Added call inside the run loop | Additive, verification-only, gated on `SNAPSHOT`/`WINDOW_CLOSE` + a present source response; never mutates factory state; full factory + lifecycle suites re-run green | Bounded-proof lane end-to-end run |

### D.11 Second-correction verdict

`V2_9_8B_POST_REPAIR_WINDOW_15M_FULL_RUN_ACCOUNTING_AND_TERMINAL_EVIDENCE_IMPLEMENTATION_PASS`

Every defect enumerated in the correction is repaired and proven by focused
disposable-DB tests with injected transports; the sealed evidence is now measured,
non-vacuous and exact. This does not authorize a live campaign. The bounded-proof
lane remains locked until operator review accepts this correction.

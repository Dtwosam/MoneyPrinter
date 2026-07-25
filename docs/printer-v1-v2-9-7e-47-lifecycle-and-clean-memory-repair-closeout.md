# Printer V1 — V2-9.7E.47 Lifecycle-Closure and Clean-Memory Repair Closeout

**Verdict: `V2_9_7E_47_LIFECYCLE_AND_CLEAN_MEMORY_REPAIR_PASS`.**

One coordinated repair lane with two implementation sections. Every listed
defect was confirmed against current code **and** against the retained
V2-9.7E.46 full-pilot evidence before any edit; no root cause differed
materially, so no `V2_9_7E_47_CONFIRMED_SCOPE_MISMATCH_STOP` was raised, and the
active source stack contained no genuine mandatory/optional contradiction, so no
`V2_9_7E_47_BLOCKED_CONTRACT_CONFLICT` was raised.

- **Starting commit:** `b7506b8110b2193d15facd9de7a3b4204ff0e417`
- **Mode:** offline repair + focused offline proof only
- **Not run:** discovery, readiness, `FULL_PILOT`, live sources, memory
  retrieval, paper decisions, any financial capability

---

## 1. Confirmed root causes

Each defect was reproduced from current code and cross-checked against a
byte-identical **disposable copy** of the retained E.46 attempt database
(`attempt.sqlite3`, SHA-256
`a29db0d9f3049b31a266ee6d28ed98708cfc896e6519954a57162cd80fa28ef3`). The
retained original was opened read-only / copied only and its SHA-256 was
re-verified unchanged after every step.

| # | Blocker | Confirmed root cause (exact owner) | Live evidence |
|---|---|---|---|
| A1 | Lifecycle-started terminal leaves `RUNNING/RUNNING/PLANNED` | `two_token_operational_pilot_runner.py:844` gated `_reconcile_pre_lifecycle_terminal_metadata` on `not lifecycle_started`, on the stated assumption that "a started lifecycle owns its own terminal reconciliation". Nothing on the started path reconciled the campaign ownership graph. | campaign `RUNNING`, run `RUNNING`, cycle `PLANNED`, all `first_terminal_cause = NULL`, while supervision was `TERMINAL` / `GOVERNED_SAFE_STOP` |
| A2 | 8 `DISCOVERY_REFRESH` jobs `PENDING` after close | Two independent faults. (a) `combined_executor._terminalize_work` updated only `printer_discovery_work`; the job it had enqueued was never transitioned. (b) `_cancel_campaign_discovery_jobs` was called with the **handoff** batch id `origin-activated:<cycle>` (`origin_lifecycle_campaign.py`) while the executor writes work under `discovery-batch:<campaign>:<run>:<cycle>`, so the query matched zero rows — and cancelling would have been the wrong terminal for succeeded work anyway. | 8/8 work rows `SUCCEEDED` with explicit causes; 8/8 linked jobs `PENDING`, no `last_error` |
| A3 | Active work undetectable | `_final_report` counted only jobs reachable through this run's factory run-steps whose status was `RUNNING` or which held a lock. `PENDING`/`COOLDOWN` were invisible, and discovery jobs were not reachable at all. | `running_jobs_after_stop = 0` was accurate under that definition and still missed all 8 |
| A4 | False `SAFE_STOP_4H_TERMINAL_INCOMPLETE` | `_four_hour_terminal_validation` required both closed 15m windows to be `CLEAN_MEMORY`/`CLEAN_DATA`/`do_not_train=0` before a natural no-continuation stop could be `complete`; a dirty window emitted `ineligible_or_dirty_terminal_15m_close` → `SAFE_STOPPED` / `STOP_TERMINAL_4H`. **Additional confirmed contributing cause:** the same branch compared `window_status != "COMPLETE"`, a value no owner writes (`e2o_memory_window_close` writes `WINDOW_CLOSED`, the audit path writes `WINDOW_AUDIT_ONLY`), so even a fully clean natural stop could never be complete. | both windows `WINDOW_CLOSED` / `DIRTY_MEMORY`; run terminated `SAFE_STOPPED` / `SAFE_STOP_4H_TERMINAL_INCOMPLETE` with `phase_state = NOT_STARTED`, no source failure, no budget breach |
| A5 | No campaign report | Neither `run_operational`, nor `OriginToLifecycleCampaignDriver`, nor the pilot runner ever invoked a campaign report owner. `handle_abstract_command` (which calls `persist_final_campaign_report`) has no caller on the pilot path. | `printer_memory_factory_campaign_reports` = **0 rows**; `reports\` directory empty |
| A6 | Dependency failure after mutable state | The PumpPortal migration transport was built at `two_token_operational_pilot_runner.py:763` — **after** `create_execution` (supervision), `build_pilot_command` (campaign/run/cycle) and the proof lock. `websockets` is declared in `pyproject.toml`, but the selected interpreter lacked it. | E.46 §2: launch died at 5.7 s with supervision `STARTING`, campaign `RUNNING`/`RUNNING`/`PLANNED`, lock left on disk, identity burned |
| B1 | Two disagreeing evidence contracts | The shared exact-ledger resolver (`context_evidence/window_15m.py`) governs six sections and can report `clean_memory_context_ready = true` with zero blockers, while the older `_classify_first_memory_review` independently dirtied the same window through a blanket "any label whose value looks UNKNOWN is a blocker" rule (`_collect_unknown_context_blockers`) that also swept in **support-only 5m** descriptors, and `_context_is_present` required a `micro_event` context row for a main window. Any non-clean result was then relabelled `MISSING_CRITICAL_DATA`. | window 2: shared resolver `clean_memory_context_ready = true`, `blockers = []`; classifier still refused it |
| B2 | Measured `+5%..+25%` becomes unknown | `classify_holding_to_15m_result` returned `HELD_TO_15M_UNKNOWN` for `held_change > 5` below the `25` threshold. | window 2 measured **+21.1217%** on **$324,448.66** liquidity and was labelled `HELD_TO_15M_UNKNOWN` |
| B3 | Known outcome erased | `_classify_first_memory_review` returned `"OUTCOME_UNKNOWN" if memory_quality != "CLEAN_MEMORY"`, discarding the truthful measured outcome. | both windows stored `outcome_label = OUTCOME_UNKNOWN` although window 1 was an unambiguous `HELD_TO_15M_DEAD` collapse |
| B4 | Negative-outcome clean eligibility | Consequence of B1 + B3: a fully evidenced collapse could not keep both a truthful adverse outcome and clean memory. | window 1 (−99.986%) stored `OUTCOME_UNKNOWN` |

---

## 2. Design contract frozen before implementation

### 2.1 Unified terminal law (Section A)

One authoritative terminal path serves **both** pre-lifecycle and
lifecycle-started termination. It reconciles campaign, campaign run, cycle,
factory run, proof supervision, every started campaign memory window, and every
campaign-scoped work row and Scheduler job. The first terminal cause is
immutable. No terminal execution may leave `campaign = RUNNING`,
`campaign run = RUNNING` or `cycle = PLANNED`.

Terminal-state mapping (frozen, `resolve_terminal_state`):

| Input | Ownership state |
|---|---|
| `run_status == COMPLETED` | `TERMINAL_COMPLETED` |
| `run_status == FAILED` | `TERMINAL_FAILED` |
| cause `PILOT_INPUT_READY` / `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED` / `PRE_LIFECYCLE_ATOMIC_TWO_SLOT_READY` / any `SAFE_STOP_*` | `TERMINAL_STOPPED` |
| anything else (blocked causes) | `TERMINAL_BLOCKED` |

Discovery work → Scheduler job parity (frozen,
`WORK_STATE_TO_JOB_ACTION`): successful work → `SUCCEEDED`; failed work →
`FAILED`; abandoned / superseded / terminally unnecessary work → `CANCELLED`.
Every transition goes through the committed Central Scheduler owner
(`complete_job` / `fail_job` / `cancel_job`). Already-terminal jobs are never
rewritten.

Lifecycle completion is separated from clean-memory success. A lawful
no-continuation close (two real 15m windows terminally closed, neither token
qualifying, no continuation required or started, no pending work, no source /
budget / integrity failure) is a **COMPLETED** governed lifecycle.
`SAFE_STOP_4H_TERMINAL_INCOMPLETE` is reserved for a continuation or required
terminal phase that actually started or was required and did not complete.
Dirty or audit-only memory blocks only the separately reported pilot
**acceptance** verdict.

### 2.2 The one WINDOW_15M evidence-quality matrix (Section B)

Derived from the active source stack, not invented:

**REQUIRED** — exact run/token/pair/window identity and current-run snapshot
ledger; complete required cadence and duration; price and liquidity fields on
every snapshot; clean snapshot source status/data quality; clean source
provenance and traces; **market regime context**; **Solana chain-heat context**;
mandatory exact-target safety evidence; entry/exit realism (quote) evidence;
trading-flow and chart evidence; and clear outcome evidence
(`held_to_15m_result_label` is derived from the **main 15m** snapshot path, so
it is required outcome evidence, not 5m evidence).

Market regime and chain heat stay **required** because Clean Master Spec §10.7
item 26 names them as critical fields and §12.4 requires every memory to link to
them. The Memory Factory Guide §12 alternative ("or explicitly recorded as
acceptable/known missing under current policy") is a conditional escape that
requires an explicit policy; no such policy exists in the active stack, so the
strict intersection of both documents is kept. This is why no
`BLOCKED_CONTRACT_CONFLICT` was raised — the documents are reconcilable, and the
conservative reading weakens nothing.

**OPTIONAL / CONTEXTUAL** — support-only 5m descriptors
(`micro_event_state_label`, `micro_event_move_label`,
`micro_exit_realism_label`, `late_buy_trap_label`,
`micro_event_payload_quality_label`, `micro_event_memory_gate_label`) and the
presence of the `micro_event` context row itself. Their absence stays an
explicit `UNKNOWN`, is reported as `optional_unknown_context`, and never
converts to `MISSING_CRITICAL_DATA` on its own. This is the permanent
`WINDOW_5M_MICRO_EVENT` support-only law (AGENTS.md; Memory Factory Guide §12A).

**Permanent outcome law:** memory quality describes evidence trustworthiness;
outcome describes what happened to the token; a bad outcome must never become
dirty merely because it was bad, and a known outcome is never erased because the
evidence around it is incomplete.

---

## 3. Files changed

| File | Change |
|---|---|
| `src/printer_v1/discovery/scheduler_parity.py` | **new** — A2 owner. `terminalize_scheduler_job_for_work` and `reconcile_discovery_work_jobs`: work→job terminal parity through the committed Scheduler owner only. |
| `src/printer_v1/operator_cli/campaign_active_work.py` | **new** — A3 owner. `campaign_scoped_job_ids` / `campaign_active_work_report`: exact campaign-scoped accounting over `PENDING`/`RUNNING`/`COOLDOWN`/locked jobs across factory run-step jobs, discovery jobs and campaign scheduler work, plus active work rows. Read-only; no Scheduler mutation. |
| `src/printer_v1/operator_cli/unified_terminal_closure.py` | **new** — A1/A5/A6 owner. `assert_runtime_dependency_preflight`, `resolve_terminal_state`, `reconcile_campaign_terminal`, `build_campaign_terminal_report`, `write_campaign_terminal_report`, `replay_campaign_terminal_report`. |
| `migrations/042_held_to_15m_moderate_continuation.sql` | **new** — B2 persistence. Rebuilds `printer_micro_events` with an identical column set/indexes; the only change is one added categorical value in the `held_to_15m_result_label` CHECK. No row rewritten, no new column. |
| `src/printer_v1/discovery/combined_executor.py` | A2 at source: `_terminalize_work` now drives the linked job terminal; `_mark_discovery_batch_failed` and the insufficient-pool bulk terminal reconcile the whole batch. |
| `src/printer_v1/operator_cli/one_command_15m_factory.py` | A2 (`_cancel_campaign_discovery_jobs` rescoped to campaign identities and parity-driven), A3 (`_final_report` exact `campaign_active_work` / `active_jobs_after_stop`, compatibility `running_or_locked_run_step_jobs`), A4 (`_four_hour_terminal_validation` separates lifecycle completion from `memory_acceptance`; `_TERMINAL_WINDOW_STATUSES`), plus `campaign_id` / `campaign_run_id` / `cycle_id` plumbing. |
| `src/printer_v1/operator_cli/origin_lifecycle_campaign.py` | Passes the exact campaign ownership identities to the lifecycle owner. |
| `src/printer_v1/operator_cli/two_token_operational_pilot_runner.py` | A6 preflight before any mutable state; A1 unified reconciliation on **every** terminal; A5 report + replay; `_emergency_terminal_closure` for post-state-creation failure; `_reconcile_pre_lifecycle_terminal_metadata` is now a thin alias over the one path. |
| `src/printer_v1/micro_event/contracts.py` | B2: adds `HELD_TO_15M_MODERATE_CONTINUATION`. |
| `src/printer_v1/micro_event/classifier.py` | B2: `(+5%, +25%)` returns the new categorical label instead of `HELD_TO_15M_UNKNOWN`. |
| `src/printer_v1/operator_cli/commands.py` | B1 (`REQUIRED_MAIN_WINDOW_CONTEXT_ENGINES`, `OPTIONAL_CONTEXT_LABELS`, `_context_is_present`, `_collect_unknown_context_blockers`, `_collect_optional_unknown_context`, evidence-driven `data_quality_label`), B3 (truthful outcome preserved independently of memory quality), B2 outcome mapping. |
| `tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py` | **new** — 39 tests / 30 subtests covering the 14 lifecycle and 10 memory proofs. |
| `tests/test_v2_9_7e_19_holder_evidence_clean_memory_repair.py` | Two tests **rewritten** (they asserted the defects): natural-stop completion now independent of memory quality; discovery cleanup now parity-driven on the real schema. |
| `tests/test_phase13_micro_event_engine.py` | Enum contract updated for the one added categorical label. |

Nothing else was touched. No policy, gate, source endpoint, retry ceiling,
lifecycle duration, liquidity floor, holder gate, continuation law, safety gate,
provenance gate, exit-realism gate or source-quality gate was weakened.

---

## 4. Real-proof-copy reconciliation (safely performed)

A byte-identical disposable copy of the retained E.46 attempt database was used.
The retained original was never opened read-write and its SHA-256 was re-verified
identical after every step.

### 4.1 Lifecycle

| Measurement | Recorded E.46 (unrepaired) | After repaired logic |
|---|---|---|
| campaign / run / cycle | `RUNNING` / `RUNNING` / `PLANNED`, causes `NULL` | `TERMINAL_STOPPED` ×3, first cause `SAFE_STOP_4H_TERMINAL_INCOMPLETE` |
| `DISCOVERY_REFRESH` jobs | 8 `PENDING` | 8 `SUCCEEDED` (8× `COMPLETE`, matching their `SUCCEEDED` work rows) |
| exact active jobs | **8** | **0** |
| terminal work attached to an active job | **8** | **0** |
| pending/running run steps | 0 | 0 |
| factory run | — | not left `RUNNING` |
| campaign report rows / artifacts | **0** / **0** | **1** / **1** |
| report-only replay | (none existed) | `new_source_calls = 0`, `new_scheduler_work = 0`, duplicates `0`, database writes `0`, artifact matches |
| integrity / FK | `ok` / 0 | `ok` / 0 |
| forbidden rows (7 tables) | 0 | 0 |

No job that was already terminal was rewritten; the two legitimately `CANCELLED`
`TRACK_NORMAL_FIRST_15M` jobs and the 18 `SUCCEEDED` lifecycle jobs are untouched.

### 4.2 Memory

The repaired classifier was replayed against each window's **recorded** context
labels, shared-resolver blockers and derived outcome context. This is a
classifier-level reconciliation on stored evidence, not a re-execution of the
full E2Q / Lane-K promotion pipeline.

| Window | Recorded measurement | Recorded result | Repaired result |
|---|---|---|---|
| 1 — `5Aybvn…pump` | `held_to_15m_price_change_percent = −99.98590`, closing liquidity `$1,337.59`; shared blocker `NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE`; raw safety `SAFETY_UNKNOWN` / `UNKNOWN` | `DIRTY_MEMORY` / `MISSING_CRITICAL_DATA` / `do_not_train=1` / `OUTCOME_UNKNOWN` | **`AUDIT_ONLY_MEMORY` / `MISSING_CRITICAL_DATA` / `do_not_train=1`**, outcome kept truthful (`HELD_TO_15M_DEAD`). Still refused — mandatory exact-target safety evidence is genuinely absent. **No safety gate weakened.** |
| 2 — `zqoFGzH…pump` | `held_to_15m_price_change_percent = +21.12172`, closing liquidity `$324,448.66`; shared resolver `clean_memory_context_ready = true`, `blockers = []`; sole recorded blocker `held_to_15m_result_label=HELD_TO_15M_UNKNOWN` | `DIRTY_MEMORY` / `MISSING_CRITICAL_DATA` / `do_not_train=1` / `OUTCOME_UNKNOWN` | **`CLEAN_MEMORY` / `CLEAN_DATA` / `do_not_train = 0`**, zero blockers, held result `HELD_TO_15M_MODERATE_CONTINUATION` |

The stored E.46 database and its historical result are **not** rewritten. The
repaired classification exists only in this disposable reconciliation.

---

## 5. Tests and checks

| Suite | Result |
|---|---|
| `test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py` (new lane) | **39 passed, 30 subtests** |
| E2Q / E2X / E2Y / E2Z / Lane K / Lane Q | **409 passed** |
| micro-event (phase 13) / outcome-evidence separation / E2V 5m evidence / E2W 5m linkage / E2U 15m closeout | **374 passed, 15 subtests** |
| Episode memory (phase 14), shared context evidence (V2-4.1), E.9 two-token lifecycle, E.11 authoritative campaign, real memory-quality audit (phase 30) | **75 passed**, 1 pre-existing failure (below) |
| Scheduler, campaign persistence, campaign ownership schema, final campaign report, durable supervision | **60 passed, 7 subtests** |
| One-command 15m factory + E.14 pilot runner + E.19 | **42 passed, 2 subtests** |
| E.14 pilot runner + E.46B readiness (independent full run) | **33 passed, 2 subtests** |
| Changed-file `py_compile` | `COMPILE_OK` |
| Import smoke through the supported interpreter | OK (`assert_runtime_dependency_preflight().status == READY`) |
| `git diff --check` | clean |
| SQLite integrity / FK on every fixture and the disposable copy | `integrity_check = ok`, `foreign_key_check = 0` |
| Migration ledger from scratch | 42 applied, `integrity ok`, FK 0, new CHECK value present |
| Static scans on added code (unowned Scheduler write, auto-restart/retry/successor, 5m authority, locked-capability activation, scoring/ranking/confidence/weighted, wallet/key/signing/live execution) | all clean |

### Pre-existing failures, confirmed against the baseline and deferred

Verified by re-running the same tests in a detached worktree at
`b7506b8` — they fail identically **before** this lane and are unrelated to it:

- `test_phase30_real_memory_quality_audit.py::test_classifier_and_readiness_report_memory_quality_audited_state` — `classify_readiness` returns `BLOCKED` because the repository-wide live-capability scan flags two long-committed files (`discovery/persistence.py: transaction_signature`, `authoritative_live_operational_campaign.py: direct_network_import:urllib.request`).
- `test_v2_9_2_terminal_budget_repair.py::test_final_report_overrides_stale_completed_reason_after_transport_failure`
- `test_v2_9_3_early_failure_accounting_repair.py::test_15m_tls_failure_is_primary_and_replay_is_zero_delta`
- `test_v2_9_3_early_failure_accounting_repair.py::test_1h_tls_failure_is_primary_and_pre_four_hour`

The last three call `_final_report` with a config carrying no `git_provenance`,
which `validate_launch_provenance` has rejected since before this lane.

Per the AGENTS.md risk-based verification policy these are documented and
deferred, not repaired here, and the full repository suite was not run.

---

## 6. Proof coverage

### Lifecycle (Section A) — all 14

1. Lifecycle-started completion terminalises campaign, run, cycle, factory run and supervision — `UnifiedTerminalReconciliationTests::test_lifecycle_started_completion_terminalises_the_whole_graph`, `PilotRunnerTerminalClosureTests::test_lifecycle_started_terminal_reconciles_and_reports`.
2. Governed safe stop terminalises the same graph — `test_governed_safe_stop_terminalises_the_same_graph`.
3. Pre-lifecycle stop still reconciles — `test_pre_lifecycle_stop_still_reconciles`, `test_pre_lifecycle_terminal_also_writes_exactly_one_report`.
4. Discovery work and linked jobs agree terminally — `DiscoverySchedulerParityTests::test_discovery_work_and_jobs_agree_terminally`, `test_factory_cleanup_scopes_by_identity_not_handoff_batch`.
5. `PENDING`, `RUNNING`, `COOLDOWN` and locked jobs all detected — `test_pending_running_cooldown_and_locked_jobs_are_all_detected`.
6. Terminal cleanup leaves zero active campaign-scoped work — `test_terminal_cleanup_leaves_zero_active_campaign_work`.
7. Lawful two-token 15m close with no continuation ends as a completed lifecycle even when memory is dirty or audit-only — `NoContinuationTerminalSemanticsTests::test_lawful_dirty_no_continuation_close_is_a_completed_lifecycle`.
8. A required or started but incomplete continuation still safe-stops — `test_started_but_incomplete_continuation_still_safe_stops`, `test_required_but_unstarted_four_hour_phase_still_safe_stops`.
9. Exactly one campaign report row and artifact — `test_lifecycle_started_terminal_reconciles_and_reports`.
10. Report-only replay: zero source calls, zero Scheduler work, no duplicate report — `test_report_only_replay_creates_no_duplicate_report`.
11. Dependency failure before mutation creates zero state — `test_dependency_failure_before_mutation_creates_zero_state`.
12. Failure after state creation reconciles everything and releases the lock — `test_failure_after_state_creation_reconciles_and_releases_the_lock`.
13. First terminal cause is immutable — `test_first_terminal_cause_is_immutable`, `test_mapping_is_frozen_and_terminal_jobs_are_never_rewritten`.
14. No restart or successor is created — `test_no_restart_or_successor_is_created`.

### Memory (Section B) — all 10

1. Fully evidenced ≈−99.99% collapse → `CLEAN_MEMORY`, truthful collapse/dead outcome, `do_not_train = 0` — `CleanMemoryEvidenceContractTests::test_fully_evidenced_collapse_becomes_clean_memory`.
2. Same collapse with missing required evidence stays dirty/audit-only — `test_the_same_collapse_with_missing_required_evidence_is_not_clean` (and the live window 1 reconciliation).
3. Favourable outcome with missing required evidence does not become clean — `test_a_favourable_outcome_with_missing_required_evidence_is_not_clean`.
4. Moderate positive 15m movement receives a known categorical held-result and outcome — `ModeratePositiveOutcomeGapTests` (5 cases across the band, plus persistence and outcome mapping).
5. Known outcomes remain known under dirty and audit-only memory — `OutcomeIndependenceTests::test_known_outcomes_survive_dirty_and_audit_only_memory` (6 outcome categories × 2 qualities).
6. Optional unknown market/chain/support-only context does not automatically become `MISSING_CRITICAL_DATA` — `test_optional_support_only_5m_unknowns_do_not_dirty_a_main_window`; mandatory market/chain heat proven still required by `test_market_and_chain_heat_context_remain_required`.
7. Missing required snapshots, exact identity, source trace, mandatory safety or required exit evidence still fail closed — `test_required_identity_source_trace_and_exit_evidence_still_fail_closed` (5 blockers).
8. Stale, conflicting, mismatched or wash-like evidence remains blocked — `test_stale_conflicting_and_wash_like_snapshot_evidence_stays_blocked`.
9. Support-only 5m remains non-authoritative — `test_5m_only_windows_can_never_become_main_memory`, plus the optional-label proof.
10. No historical evidence rewritten, no locked capability activated — `NoLockedCapabilityActivationTests`; retained E.46 SHA-256 re-verified unchanged.

---

## 7. Money-usefulness contribution

This lane converts the first live end-to-end pilot from an unreadable terminal
into a governed, closable, reportable one, and it produces the program's first
clean memory from real recorded evidence.

- On the retained real E.46 evidence the repaired logic turns
  `8 active jobs / RUNNING-RUNNING-PLANNED / 0 reports` into
  `0 active jobs / TERMINAL_STOPPED ×3 / exactly 1 report row + 1 artifact`,
  with a deterministic zero-source replay. A future pilot can now be *closed and
  audited*, not just executed.
- Window 2 — a real token that genuinely held **+21.12%** to 15 minutes on
  **$324,448.66** of exact-pool liquidity, with the shared exact-ledger resolver
  already reporting zero blockers — becomes **`CLEAN_MEMORY`**. Under the old
  contract it was thrown away solely because its measured gain fell between two
  categorical thresholds. That is one genuine clean memory recovered from
  evidence Printer already paid for.
- Window 1 — a real −99.986% rug — keeps its truthful `HELD_TO_15M_DEAD` outcome
  instead of `OUTCOME_UNKNOWN`, and is still refused as training material
  because its mandatory safety evidence is genuinely absent. Printer now
  remembers *what happened* even when it cannot trust *how it was measured*.
- Separating lifecycle completion from clean-memory acceptance means a lawful
  no-continuation cycle no longer masquerades as a 4h failure, so operators stop
  spending attempts chasing a phantom terminal defect.

No profit, trade-quality, retrieval or decision claim is made. Zero clean memory
was written to any corpus by this lane.

---

## 8. What improved

- One authoritative terminal path for every pilot terminal, pre-lifecycle and
  lifecycle-started alike, preserving the immutable first cause.
- Discovery work and Scheduler jobs can no longer disagree; parity is driven by
  the work row's own terminal state through the committed Scheduler owner.
- Exact campaign-scoped active-work accounting replaces a count that could not
  see `PENDING`, `COOLDOWN`, locked or discovery jobs.
- Lifecycle completion and clean-memory acceptance are separate verdicts.
- Every terminal outcome now produces exactly one persistent report row and one
  durable artifact with a deterministic zero-source replay.
- A dependency/interpreter fault now blocks before a single mutable row exists;
  a post-state fault closes through the same terminal path and releases the lock.
- One evidence-quality contract for `WINDOW_15M`, with support-only 5m evidence
  explicitly unable to dirty a main window.
- A measured `(+5%, +25%)` trajectory is a known categorical result.
- Outcome is persisted independently of memory quality.

## 9. What remains locked

Solana-only; Solana memecoin-only; paper-only; no wallet, private key, signing,
real funds or live execution; no paid dependency; no scoring, ranking,
confidence or weighted logic; no embeddings or vectors; no Source Governor or
Central Scheduler bypass; no retrieval activation; no paper decisions; no
BUY/SELL/HOLD; no positions, trade events, paper audits or PnL; no dirty-memory
retrieval or decision use; 5m support-only; no automatic retry, restart or
successor.

## 10. Proof still required

- Live confirmation that a lifecycle-started terminal leaves
  `TERMINAL/TERMINAL/TERMINAL` with zero active jobs and one report — proved
  offline and against recorded evidence, never observed on a live run.
- `WINDOW_1H` / `WINDOW_4H` continuation and the `COMPLETED` 4h terminal path
  remain live-unproven; no cycle has yet qualified for continuation.
- Live confirmation that a real 15m window reaches `CLEAN_MEMORY` end-to-end
  through E2Q → Lane K → E2Z promotion (this lane proved the classifier decision
  on recorded evidence, not the full promotion pipeline).
- Live confirmation of the A6 preflight refusing an incomplete interpreter.
- Context coverage for `liquidity_lock_or_burn_label` and
  `known_risk_flag_label`, which both E.46 windows reported as pending.

---

## 11. Functionality Risks / Setbacks / Efficiency Blockers

- **Functionality risk:** `reconcile_campaign_terminal` cancels remaining active
  campaign-scoped jobs through the Scheduler owner. If a future owner enqueues a
  campaign-attributable job that is legitimately meant to outlive the campaign
  terminal, it would be cancelled. No such job exists today; the scope is
  campaign/run/cycle-bound by identity.
- **Functionality risk:** market regime and chain-heat context stay mandatory.
  If live coverage for them remains weak, clean memory remains hard to reach even
  after this repair. That is a deliberate, spec-backed choice, not an oversight —
  relaxing it requires an explicit operator policy decision, which this lane did
  not take.
- **Setback:** the A5 report uses the `campaign_persistence` terminal-report
  owner rather than `final_campaign_report.persist_final_campaign_report`. The
  latter demands the full 6B campaign-object graph (campaign objects of every
  kind, campaign windows, campaign scheduler work, campaign supervision rows)
  which the pilot path has never created. Wiring that graph is a separate lane;
  inventing it here would have fabricated evidence.
- **Setback:** migration 042 rebuilds `printer_micro_events`. Nothing references
  it by foreign key and the rebuild was verified (`integrity ok`, FK 0, 42
  migrations from scratch), but any external tooling holding a hard-coded
  `printer_micro_events` rowid assumption should be re-checked.
- **Setback:** four pre-existing test failures remain (§5). The
  `classify_readiness` one in particular means the operator readiness check
  reports `BLOCKED` on this repository irrespective of this lane.
- **Efficiency blocker:** none introduced. The affected suites are slow
  (E2Q/Lane-K ≈ 23 min, pilot runner ≈ 6 min); they were run in parallel
  background batches rather than as one serial sweep.
- **Observation:** `unified_terminal_closure` writes
  `printer_memory_factory_runs.run_status` directly when a factory run is left
  `RUNNING`, mirroring the pre-existing `proof_supervision._zero_source_cleanup`
  behaviour. That is the factory-run owner table, not a Scheduler bypass.

---

## 12. Readiness for one separately authorised full-pilot attempt

**Ready.** A PASS here authorises *consideration* of exactly one fresh full-pilot
attempt; this lane did not run it, did not start V2-9.7F and did not start
V2-9.8.

Before that attempt the operator should note:

- the executing interpreter must satisfy the declared dependency set — the A6
  preflight now enforces this before any authorization is consumed;
- BL-46-01 (holder evidence) is an environment/configuration condition, not a
  code defect, and still requires a working `PRINTER_HELIUS_API_KEY` or a
  responsive public RPC;
- live migration supply remains sparse and bursty (BL-43-01);
- a lawful two-token no-continuation close will now report `COMPLETED` with a
  separate `memory_acceptance` verdict, so a dirty memory result must be read as
  an acceptance block, not a lifecycle failure.

**V2-9.7E remains the active lane. V2-9.7F is not started.**

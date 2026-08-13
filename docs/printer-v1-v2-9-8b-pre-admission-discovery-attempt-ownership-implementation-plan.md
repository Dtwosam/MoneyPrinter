# Printer V1 V2-9.8B Pre-Admission Discovery Attempt Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to execute this plan task-by-task.

**Goal:** Resolve the durable pre-admission discovery-attempt blocker, then resume later-cycle callback binding, atomic cycle-2 consumption, and frozen-evidence materialization without creating cycle 2 before discovery or running the four-token proof.

**Architecture:** Add one additive pre-admission ownership ledger rooted in campaign/run/authoritative-factory identity, one dedicated low-priority Scheduler job kind, and one exact-two-item frozen-pair boundary. Reuse existing Eligible Token Supply, holder/fixed-gate, uniform-selection, Source Governor, Scheduler, and multi-cycle coordinator owners; do not relax existing cycle-rooted discovery tables.

**Tech stack:** Python 3, SQLite migrations, existing Printer V1 Scheduler/Source Governor/discovery/coordinator modules, pytest.

## Global constraints

- Starting baseline: `0979cbb29b3ad120b7c302436c03898d79232715`.
- Active design: `docs/printer-v1-v2-9-8b-pre-admission-discovery-attempt-ownership-design.md`.
- Additive migration only; do not rebuild or relax migrations 034/050/054.
- Do not apply migration 055 to the authoritative operational DB in this implementation batch.
- No live source fetching, no operational Scheduler execution, no proof authorization, no four-token runtime.
- No retry/restart/successor attempt; one durable opportunity for proposed cycle ordinal 2.
- `TOKEN_CAPACITY` remains 2; provider ceilings unchanged; no 12h/24h, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
- Preserve untracked operator authorization artifacts untouched.
- Use focused RED→GREEN tests per task. Stop immediately on an authority/parity blocker.

---

### Task 1 — Additive schema + Scheduler contract

**Files**
- Create: `migrations/055_pre_admission_discovery_attempt_ownership.sql`
- Modify: `src/printer_v1/scheduler/contracts.py`
- Test: `tests/test_v2_9_8b_pre_admission_discovery_attempt_schema.py`

**Produces**
- `JobKind.PRE_ADMISSION_DISCOVERY_SELECTION`
- `printer_pre_admission_discovery_attempts`
- `printer_pre_admission_discovery_attempt_items`
- `printer_pre_admission_discovery_attempt_source_links`

- [ ] RED: prove migration 055 and the new Scheduler kind are absent.
- [ ] GREEN: add `PRE_ADMISSION_DISCOVERY_SELECTION` immediately after `DISCOVERY_REFRESH` in `JOB_PRIORITY_ORDER`, so it remains below all lifecycle/close work.
- [ ] GREEN: add migration 055 with campaign/run/configuration/factory/Scheduler FKs, no pre-consumption cycle FK, unique `(campaign_id,campaign_run_id,authoritative_factory_run_id,proposed_cycle_ordinal)`, strict active/terminal state invariants, slot ordinal constraints, source-link provenance constraints, and consumed-cycle binding only for `CONSUMED`.
- [ ] Verify fresh migration-chain application in a disposable DB, `foreign_key_check`, `integrity_check`, one-attempt uniqueness, terminal invariants, and no rebuild/mutation of existing tables.
- [ ] Commit RED and GREEN separately.

**STOP:** if migration 055 is occupied at execution time, use the next free number before production changes and document the factual reason.

---

### Task 2 — Pure pre-admission attempt persistence owner

**Files**
- Create: `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`
- Test: `tests/test_v2_9_8b_pre_admission_discovery_attempt_persistence.py`

**Interfaces**
- `PreAdmissionAttemptState`
- immutable `PreAdmissionDiscoveryAttempt`
- immutable `PreAdmissionAttemptItem`
- `create_pre_admission_attempt(...)`
- `mark_pre_admission_attempt_running(...)`
- `terminalize_pre_admission_attempt(...)`
- `persist_pre_admission_pair(...)`
- `link_pre_admission_source_evidence(...)`
- `load_pre_admission_attempt(...)`
- `load_pre_admission_pair(...)`

- [ ] RED: one-shot uniqueness, wrong campaign/run/factory ownership, invalid state transitions, partial pair, duplicate identities, source response/failure ambiguity, terminal rewrite, and terminal→active reopening all fail.
- [ ] GREEN: implement strict compare-and-update persistence only; no Scheduler calls and no source calls.
- [ ] Pair persistence must require exactly two distinct items and transition to `PAIR_READY` atomically; no committed one-item intermediate state.
- [ ] Source links reference canonical source ledger IDs only; never infer ownership from request keys.
- [ ] Commit RED and GREEN separately.

---

### Task 3 — Scheduler ownership + active-work visibility

**Files**
- Modify: `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`
- Modify: `src/printer_v1/operator_cli/campaign_active_work.py`
- Test: `tests/test_v2_9_8b_pre_admission_discovery_attempt_scheduler.py`

**Produces**
- `create_scheduled_pre_admission_attempt(...)`
- active-work projection includes `PLANNED`/`RUNNING` pre-admission attempts.

- [ ] RED: attempt creation without exact Scheduler ownership, duplicate active attempt/job, wrong factory identity, and cleanup invisibility fail.
- [ ] GREEN: create the canonical Scheduler job and `PLANNED` attempt in one transaction using `PRE_ADMISSION_DISCOVERY_SELECTION`; target the attempt identity, not a fabricated cycle/window/slot.
- [ ] GREEN: `RUNNING` transition requires the exact canonical Scheduler claim/lock owner.
- [ ] GREEN: campaign active-work/terminal cleanup inspection counts active attempt work but never terminal attempts.
- [ ] Scheduler calls in this task are disposable ownership fixtures only; no operational Scheduler runtime.
- [ ] Commit RED and GREEN separately.

---

### Task 4 — Factor existing holder/fixed-gate/uniform-selection authority

**Files**
- Modify: `src/printer_v1/discovery/combined_executor.py`
- Test: `tests/test_v2_9_8b_pre_admission_selection_authority_parity.py`
- Reuse affected existing combined-discovery tests.

**Produces**
- a public owner-local helper in `combined_executor.py` that applies the existing holder/safety, fixed-gate, and deterministic uniform-selection law without performing handoff.
- both the existing cycle-rooted executor and the pre-admission callback call this same helper.

- [ ] RED: freeze representative existing accepted/rejected cases, rejection causes, and deterministic pair output from the current combined executor.
- [ ] GREEN: factor the existing `_apply_gates` / selection behavior into the shared helper without changing categorical rules, gate order, rejection causes, or seed semantics.
- [ ] GREEN: the existing cycle-rooted executor must call the shared helper and retain byte-/identity-equivalent selected results.
- [ ] No copied holder/fixed-gate policy; no scores/ranks/confidence/weights.
- [ ] Commit RED and GREEN separately.

**STOP:** if a narrow helper cannot preserve exact behavior, stop with the precise owner dependency rather than creating a parallel eligibility policy.

---

### Task 5 — One-shot later-cycle discovery callback

**Files**
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify: `src/printer_v1/operator_cli/four_token_proof_integration.py`
- Reuse: `src/printer_v1/discovery/eligible_token_supply.py`
- Reuse: Task-4 shared selection helper.
- Test: `tests/test_v2_9_8b_pre_admission_later_cycle_callback.py`

**Produces**
- one authoritative later-cycle callback result carrying one durable `attempt_id` and either a frozen exact pair or honest terminal no-pair/block/failure/cancel evidence.

- [ ] RED: no callback can start without exact campaign/run/factory/opportunity identity, authoritative health, and exact Scheduler claim.
- [ ] RED: repeated invocation for the same proposed cycle opportunity cannot create or execute a second attempt.
- [ ] GREEN: use the existing governed Eligible Token Supply acquisition under the same Source Governor/Central Scheduler owners, then existing holder evidence and Task-4 shared gate/selection helper; link every provider-reaching source fact to the attempt.
- [ ] GREEN: terminalize exactly once as `PAIR_READY`, `NO_PAIR`, `BLOCKED`, `FAILED`, or `CANCELLED`.
- [ ] No cycle-2 row, slot, first-15m job, retry, restart, successor, polling loop, or second runner.
- [ ] Commit RED and GREEN separately.

---

### Task 6 — Atomic cycle-2 consumption

**Files**
- Modify: `src/printer_v1/operator_cli/multi_cycle_campaign_coordinator.py`
- Reuse: `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`
- Test: `tests/test_v2_9_8b_pre_admission_atomic_cycle2_consumption.py`

**Produces**
- `admit_two_token_cycle_from_attempt(...)`.

- [ ] RED: stale health/session state, consumed attempt, wrong ordinal/factory/configuration, partial pair, historical identity reuse, or changed admission decision rolls back with no cycle and no consumption.
- [ ] GREEN: inside one fresh `BEGIN IMMEDIATE`, reload session/admission state, require exact unconsumed `PAIR_READY`, load exactly two frozen items, delegate to existing exact two-token cycle creation authority, then bind `consumed_cycle_id` and transition to `CONSUMED` before commit.
- [ ] Failed/deferred admission leaves the attempt unconsumed and never reruns discovery.
- [ ] Prove exactly cycle ordinal 2, exactly two slots, no historical identity reuse, and no third cycle.
- [ ] Commit RED and GREEN separately.

---

### Task 7 — Frozen-evidence cycle-rooted materialization

**Files**
- Modify: `src/printer_v1/discovery/combined_executor.py`
- Create: `src/printer_v1/discovery/pre_admission_materialization.py`
- Test: `tests/test_v2_9_8b_pre_admission_frozen_pair_materialization.py`

**Produces**
- `materialize_consumed_pre_admission_pair(...)` in `pre_admission_materialization.py`.
- a reusable cycle-rooted selection/handoff persistence primitive factored from the existing combined executor, so the normal executor and materializer share the same persistence law.

- [ ] RED: reject unconsumed attempts, identity/evidence drift, wrong cycle/factory, extra source requests, selector invocation, and pair substitution.
- [ ] GREEN: factor the existing selection/handoff persistence boundary from `CombinedPumpfunCampaignExecutor` without altering existing cycle-1 behavior.
- [ ] GREEN: materialize normal cycle-2 discovery/selection/handoff ownership from the frozen consumed attempt and its linked source evidence only.
- [ ] No discovery source request and no selection call during materialization.
- [ ] Prove compatibility with existing cycle-aware `t1_c0002_*` / `t2_c0002_*` ownership namespace.
- [ ] Commit RED and GREEN separately.

---

### Task 8 — Prerequisite integrated closeout

**Files**
- Create: `docs/printer-v1-v2-9-8b-pre-admission-discovery-attempt-ownership-closeout.md`

- [ ] Run the minimum integrated tests for schema, persistence, Scheduler ownership, active-work visibility, combined-discovery parity, one-shot callback, atomic cycle-2 consumption, frozen materialization, and directly affected four-token disposition/controller contracts.
- [ ] Run `py_compile` on touched Python modules and `git diff --check`.
- [ ] Confirm migration 055 was not applied to the authoritative operational DB.
- [ ] Confirm zero live source execution, zero real Scheduler runtime, zero proof authorization/run, unchanged `TOKEN_CAPACITY==2`, unchanged provider ceilings, and untouched untracked authorization artifact.
- [ ] Close with exactly one verdict:
  - `V2_9_8B_PRE_ADMISSION_DISCOVERY_ATTEMPT_OWNERSHIP_PASS_READY_FOR_FACTORY_LOOP_INTEGRATION_REVIEW`
  - or `BLOCKED_<EXACT_REASON>`.
- [ ] Push the same implementation branch and STOP.

## Stop boundary

Do not implement canonical factory-loop wake integration in this plan. Do not run or authorize the four-token proof. Factory-loop integration resumes only after this prerequisite closeout is independently reviewed and accepted.

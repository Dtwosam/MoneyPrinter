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

- [ ] RED: prove migration 055 is absent and the new Scheduler kind is absent.
- [ ] GREEN: add the dedicated Scheduler kind after `DISCOVERY_REFRESH` in `JOB_PRIORITY_ORDER`, below all lifecycle/close work.
- [ ] GREEN: add migration 055 with campaign/run/configuration/factory/Scheduler FKs, no pre-consumption cycle FK, unique `(campaign_id,campaign_run_id,authoritative_factory_run_id,proposed_cycle_ordinal)`, strict active/terminal state invariants, exact slot ordinal constraints, immutable source-link provenance constraints, and nullable consumed-cycle binding only for `CONSUMED`.
- [ ] Verify fresh migration-chain application in disposable DB, `foreign_key_check`, `integrity_check`, one-attempt uniqueness, terminal invariants, and no mutation/rebuild of existing tables.
- [ ] Commit RED and GREEN separately.

**STOP:** if migration number 055 is already occupied at execution time, renumber to the next free migration before any production change and document it.

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
- [ ] Pair persistence must require exactly two distinct slot items and transition to `PAIR_READY` atomically; no one-item intermediate committed state.
- [ ] Source links must reference existing canonical source ledgers only; never infer ownership from request keys.
- [ ] Commit RED and GREEN separately.

---

### Task 3 — Scheduler ownership + active-work visibility

**Files**
- Modify: `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`
- Modify: `src/printer_v1/operator_cli/campaign_active_work.py`
- Test: `tests/test_v2_9_8b_pre_admission_discovery_attempt_scheduler.py`

**Produces**
- atomic helper `create_scheduled_pre_admission_attempt(...)`
- active-work projection includes `PLANNED`/`RUNNING` pre-admission attempts.

- [ ] RED: prove attempt creation without exact Scheduler ownership, duplicate active attempt/job, wrong factory identity, and cleanup invisibility fail.
- [ ] GREEN: create the canonical Scheduler job and `PLANNED` attempt in one transaction using `PRE_ADMISSION_DISCOVERY_SELECTION`; target the attempt identity, not a fabricated cycle/window/slot.
- [ ] GREEN: claim transition must require the exact canonical Scheduler job/lock owner before `RUNNING`.
- [ ] GREEN: campaign active-work/terminal cleanup inspection must count active attempt work without treating terminal attempts as active.
- [ ] No Scheduler execution in tests beyond fixture/disposable Scheduler ownership operations.
- [ ] Commit RED and GREEN separately.

---

### Task 4 — Factor existing holder/fixed-gate/uniform-selection authority

**Files**
- Modify: `src/printer_v1/discovery/combined_executor.py`
- Create only if needed for a clean shared boundary: `src/printer_v1/discovery/operational_selection_authority.py`
- Test: `tests/test_v2_9_8b_pre_admission_selection_authority_parity.py`
- Reuse affected existing combined-discovery tests.

**Produces**
- one shared owner-local function for the existing holder/safety + fixed-gate + deterministic uniform-selection behavior, callable by both cycle-rooted and pre-admission paths.

- [ ] RED: capture representative existing accepted/rejected candidate cases and deterministic selected-pair output from the current combined executor.
- [ ] GREEN: factor existing predicates/selection without changing their categorical rules, order, rejection causes, or uniform-selection seed semantics.
- [ ] Prove the existing cycle-rooted executor produces the same results before/after factoring.
- [ ] Do not copy holder/fixed-gate logic into a second policy and do not add scores/ranks/confidence/weights.
- [ ] Commit RED and GREEN separately.

**STOP:** if exact behavioral parity cannot be maintained with a narrow factoring seam, stop with the precise owner dependency instead of implementing a parallel selection policy.

---

### Task 5 — One-shot later-cycle discovery callback

**Files**
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` or the current authoritative callback owner found at execution time.
- Modify: `src/printer_v1/operator_cli/four_token_proof_integration.py`
- Reuse: `src/printer_v1/discovery/eligible_token_supply.py`
- Reuse: shared selection authority from Task 4.
- Test: `tests/test_v2_9_8b_pre_admission_later_cycle_callback.py`

**Produces**
- callback result that references one durable `attempt_id` and returns either frozen exact pair evidence or honest terminal no-pair/block/failure/cancel.

- [ ] RED: prove no callback can run without exact campaign/run/factory/opportunity identity and exact Scheduler claim.
- [ ] RED: repeated invocation for the same opportunity must not create or execute a second attempt.
- [ ] GREEN: run the existing governed Eligible Token Supply acquisition under the same Source Governor, then shared holder/fixed-gate/uniform-selection authority, linking all provider-reaching source evidence to the attempt.
- [ ] GREEN: terminalize once as `PAIR_READY`, `NO_PAIR`, `BLOCKED`, `FAILED`, or `CANCELLED`.
- [ ] No cycle-2 row, token slot, first-15m job, retry, restart, successor, independent polling loop, or second runner.
- [ ] Commit RED and GREEN separately.

---

### Task 6 — Atomic cycle-2 consumption

**Files**
- Modify: `src/printer_v1/operator_cli/multi_cycle_campaign_coordinator.py`
- Reuse: `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py`
- Test: `tests/test_v2_9_8b_pre_admission_atomic_cycle2_consumption.py`

**Produces**
- `admit_two_token_cycle_from_attempt(...)` or equivalently narrow composition around existing coordinator authority.

- [ ] RED: stale health/session state, consumed attempt, wrong ordinal/factory, partial pair, historical identity reuse, or changed admission decision must rollback with no cycle and no consumption.
- [ ] GREEN: inside the coordinator's single `BEGIN IMMEDIATE`, reload health/session, require exact unconsumed `PAIR_READY`, load exactly two frozen items, call existing exact two-token cycle creation authority, then bind `consumed_cycle_id` and transition to `CONSUMED` before commit.
- [ ] If admission cannot proceed, leave the attempt unconsumed and do not rerun discovery.
- [ ] Prove exactly cycle ordinal 2 / exactly two slots / no identity reuse / no third cycle.
- [ ] Commit RED and GREEN separately.

---

### Task 7 — Frozen-evidence cycle-rooted materialization

**Files**
- Modify the smallest existing cycle-rooted discovery/handoff persistence owner, expected `src/printer_v1/discovery/combined_executor.py` and/or `src/printer_v1/discovery/persistence.py`.
- Test: `tests/test_v2_9_8b_pre_admission_frozen_pair_materialization.py`

**Produces**
- materialization helper that converts a consumed immutable attempt into normal cycle-2 discovery/selection/handoff ownership without refetching or reselection.

- [ ] RED: prove materialization rejects unconsumed attempts, identity/evidence drift, wrong cycle/factory, extra source requests, and pair substitution.
- [ ] GREEN: create the normal cycle-rooted discovery/selection/handoff evidence from frozen attempt data, preserving source lineage and exact selected identities.
- [ ] No discovery source request and no selector call may occur during materialization.
- [ ] Prove cycle-aware step/Scheduler ownership remains compatible with existing `t1_c0002_*` / `t2_c0002_*` namespace.
- [ ] Commit RED and GREEN separately.

---

### Task 8 — Prerequisite integrated closeout

**Files**
- Create: `docs/printer-v1-v2-9-8b-pre-admission-discovery-attempt-ownership-closeout.md`

- [ ] Run the minimum integrated tests covering schema, persistence, Scheduler ownership, active-work visibility, existing discovery parity, one-shot callback, atomic cycle-2 consumption, frozen materialization, and existing four-token disposition/controller tests directly affected.
- [ ] Run `py_compile` on touched Python modules and `git diff --check`.
- [ ] Confirm migration 055 was **not** applied to the authoritative operational DB.
- [ ] Confirm zero live source execution, zero real Scheduler runtime, zero proof authorization/run, unchanged `TOKEN_CAPACITY==2`, unchanged provider ceilings, and untouched untracked authorization artifact.
- [ ] Close with exactly one verdict:
  - `V2_9_8B_PRE_ADMISSION_DISCOVERY_ATTEMPT_OWNERSHIP_PASS_READY_FOR_FACTORY_LOOP_INTEGRATION_REVIEW`
  - or `BLOCKED_<EXACT_REASON>`.
- [ ] Push the same implementation branch and STOP.

## Stop boundary

Do **not** implement canonical factory-loop wake integration in this plan. Do not run or authorize the four-token proof. Factory-loop integration resumes only after this prerequisite closeout is independently reviewed and accepted.

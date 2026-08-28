# 4/2/2 Orchestration Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair and bounded-test the four product defects proven by the consumed V2-9.8B 4/2/2 campaign without live execution or authoritative DB mutation.

**Architecture:** Reuse the existing campaign-window, pre-admission attempt, Central Scheduler, temporal refresh, Source Governor, StageBudget, and full-run accounting owners. Add only an identity-only 1h bind and an append-only attempt-evidence table; cooperative acquisition advances one missing Source-Governed request per existing Scheduler claim.

**Tech Stack:** Python 3, SQLite additive migrations, pytest/unittest, Printer V1 Source Governor and Central Scheduler contracts.

**Spec:** `docs/printer-v1-v2-9-8b-4-2-2-orchestration-correctness-design.md` plus `docs/printer-v1-v2-9-8b-cycle-2-cooperative-acquisition-design-amendment.md`

## Global Constraints

- No authorization creation or live Printer/Scheduler/provider execution.
- Never mutate `data/printer_v1.sqlite3`; tests use disposable migrated SQLite files.
- Preserve all V1 safety, exact-pair, liquidity, evidence, accounting, and capability locks.
- Strict RED -> GREEN per defect; run the focused failing test before product code.
- Migration 062 is additive and contains only the attempt-evidence ledger.

---

### Task 1: Bind owned WINDOW_1H before E2Z

**Files:**
- Modify: `src/printer_v1/operator_cli/operational_selective_1h.py`
- Modify: `src/printer_v1/operator_cli/one_command_15m_factory.py`
- Test: `tests/test_v2_9_8b_4_2_2_orchestration_correctness.py`

**Interfaces:**
- Produces: `bind_precreated_1h_campaign_window_memory_row(connection, *, campaign_id, run_id, cycle_id, token_slot_id, token_row_id, pair_row_id, campaign_window_id, memory_window_row_id, now=None) -> dict[str, Any]`
- Produces: `_bind_precreated_1h_campaign_window_before_e2z(conn, *, step, memory_window_row_id) -> dict[str, Any] | None`

- [ ] Write tests proving bind-before-E2Z visibility, same-id idempotency, wrong physical identity rejection, conflicting identity rejection, and ambiguous owner rejection.
- [ ] Run `pytest -q tests/test_v2_9_8b_4_2_2_orchestration_correctness.py -k 'one_hour'` and record the missing-helper/order RED failure.
- [ ] Implement the identity-only helper and insert bind/commit/readback between E2Q audit and E2Z.
- [ ] Run the focused tests and the nearest 15m/1h/4h progression tests GREEN.
- [ ] Commit the test and repair.

### Task 2: Refine cooperative acquisition to one governed request

**Files:**
- Modify: `src/printer_v1/discovery/direct_migration_discovery.py`
- Modify: `src/printer_v1/discovery/eligible_token_supply.py`
- Modify: `src/printer_v1/discovery/pre_lifecycle_refresh_composition.py`
- Modify: `src/printer_v1/operator_cli/pre_lifecycle_persistent_refresh_owner.py`
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify where needed: `src/printer_v1/operator_cli/one_command_15m_factory.py`
- Test: `tests/test_v2_9_8b_4_2_2_orchestration_correctness.py`

**Interfaces:**
- Produces: a cooperative direct-migration call that replays exact terminal request keys, issues at most one absent request, returns `ACQUISITION_QUANTUM_YIELDED` with the next governed-request bound, and promotes/advances only when complete.
- Produces: refresh owner support for `CLAIMED wait + RUNNING work + yielded PENDING Scheduler job` under the same identities.

- [ ] Write RED tests for the 115-second TRACK_FAST conflict, next-request fit, one-call ceiling, replay without reissue, unsplit PumpSwap governed request, lifecycle/horizon preemption, and fixed refresh anchors.
- [ ] Run the Cycle-2 focused selection and confirm expected RED failures.
- [ ] Add terminal request reconstruction and one-new-request enforcement without a new Scheduler/source owner or generic quantum table.
- [ ] Make delayed refresh work yield/reclaim the same owner and keep absolute opportunity times anchored to attempt start.
- [ ] Run focused Cycle-2 tests and adjacent cadence/temporal/direct-migration regressions GREEN.
- [ ] Commit the test and repair.

### Task 3: Persist and reduce attempt-owned terminal evidence

**Files:**
- Create: `migrations/062_pre_admission_attempt_evidence.sql`
- Create: `src/printer_v1/operator_cli/pre_admission_attempt_evidence.py`
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify: `src/printer_v1/discovery/eligible_token_supply.py`
- Test: `tests/test_v2_9_8b_4_2_2_orchestration_correctness.py`
- Update: focused migration-head/coherence tests that canonically name migration 061.

**Interfaces:**
- Produces: append-only deterministic categorical attempt events bound to attempt/opportunity/subject/source lineage.
- Produces: `reduce_pre_admission_attempt_evidence(connection, *, attempt_id) -> AttemptEvidenceSummary`.

- [ ] Write RED tests for cross-claim candidates, categorical rejections, provider failures, refresh opportunities, deduplication, and nonzero certificate reconstruction.
- [ ] Run the Defect-3 focused selection and confirm table/module absence RED failures.
- [ ] Add migration 062, idempotent append validation, source-lineage triggers, reducer, and callback/supply persistence hooks.
- [ ] Rebuild terminal diagnostics/certificate fields from the durable reducer rather than final-call locals.
- [ ] Run focused evidence and canonical migration-order/digest tests GREEN.
- [ ] Commit the migration, tests, and repair.

### Task 4: Reconcile every transport and cumulative pre-close reservation

**Files:**
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify: `src/printer_v1/operator_cli/one_command_15m_factory.py`
- Modify: `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- Test: `tests/test_v2_9_8b_4_2_2_orchestration_correctness.py`

**Interfaces:**
- Consumes: existing action-local `transport_identity_observer`.
- Produces: cumulative ordered `lifecycle_reservations` in each pre-close result and strict reconstruction of those exact reservations.

- [ ] Write RED tests for later-cycle holder observer wiring, exactly-once action-local identities, two preserved pre-close reservations, strict reconciliation success, and missing-observer failure.
- [ ] Run the Defect-4 focused selection and confirm expected RED failures.
- [ ] Forward the active observer to later-cycle holder evaluation and merge prior exact reservation records on each claim.
- [ ] Validate/reconstruct pre-close reservation owner identities from the cumulative manifest while leaving bidirectional equality strict.
- [ ] Run focused accounting and adjacent full-run accounting regressions GREEN.
- [ ] Commit the test and repair.

### Task 5: Focused bounded proof and closeout

**Files:**
- Create: `docs/printer-v1-v2-9-8b-4-2-2-orchestration-correctness-implementation-closeout.md`
- Modify: `AGENTS.md`
- Modify: `CURRENT_HANDOFF.md`

- [ ] Run the complete focused correctness file and all directly adjacent test modules listed by the operator.
- [ ] Run `python -m compileall -q src/printer_v1` (with bytecode directed outside the repository if needed) and `git diff --check`.
- [ ] Verify the authoritative DB SHA, immutable integrity/FK checks, absence of DB sidecars, and process quiescence.
- [ ] Inspect the migration for additive-only scope and confirm it was applied only to disposable test DBs.
- [ ] Write the exact PASS or BLOCKED closeout from fresh evidence and synchronize governance/handoff to the next separate decision lane.
- [ ] Commit proof/closeout and report exact commits, files, counts, migration status, DB hashes, blockers, and next lane.

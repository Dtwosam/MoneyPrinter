# WINDOW_15M Freeze / Holder-Budget Decoupling Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the full bounded market/protocol observation universe while collecting only the truthful holder context that fits the unchanged 45-operation campaign ceiling.

**Architecture:** Project exact pre-holder request and measured-transport truth from the existing campaign accounting owners into an immutable snapshot. Build the holder ledger from independent request and transport counts, decouple permanent admission from `candidate_cap()`, and make permanent holder attempts stop categorically before an unaffordable request while carrying explicit budget-bound unknown context into the unchanged freeze owner.

**Tech Stack:** Python 3.11+, dataclasses, SQLite, pytest, existing Source Governor/Central Scheduler/campaign six-unit owners.

## Global Constraints

- Preserve operation ceiling `45`, zero-transport charge `9`, reservations `2 + 4`, holder pre-attempt requirement `5`, permanent holder-stage ceiling `8`, and `MINIMUM_FREEZE_DEPTH = 4`.
- No authoritative database mutation, provider network, real authorization, retry, recovery, successor, scoring, ranking, confidence, weighting, retrieval, trading, wallet, signing, or financial capability.
- Use existing Source Governor, Central Scheduler, campaign six-unit accounting, holder persistence, observation conversion, and freeze owners.
- Stop on the first contradictory accounting identity or continuous-proof blocker.

---

### Task 1: Exact accounting projection and independent ledger counts

**Files:**
- Modify: `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- Modify: `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- Test: `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py`

**Interfaces:**
- Produces: immutable `PreHolderBudgetSnapshot`, `build_pre_holder_budget_snapshot(...)`, and `build_ledger_from_exact_counts(governed_request_count, underlying_transport_operations, deadline_at)`.
- Consumes: existing campaign-owner transports, action-local transports, durable Source Governor request manifest, and fixed reservation constants.

- [ ] Write focused tests for independent request/transport counts, measured-operation charging, duplicate/missing/mismatched identity rejection, and legacy equality compatibility.
- [ ] Run the focused nodes and verify they fail for missing exact-count/snapshot behavior.
- [ ] Implement the minimal immutable projection, reconciliation, and exact-count ledger path.
- [ ] Run the focused nodes and verify they pass.

### Task 2: Permanent admission and incremental holder-context collection

**Files:**
- Modify: `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify: `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- Test: `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py`

**Interfaces:**
- Produces: immutable `HolderAttemptAdmission`, non-mutating `holder_attempt_admission(...)`, and extended `HolderContextResult` diagnostics.
- Consumes: permanent-mode flag, full bounded graduated universe, exact ledger, existing governed holder bundle and holder persistence owner.

- [ ] Write focused tests proving four permanent candidates survive a holder cap of three while legacy admission is unchanged.
- [ ] Write focused tests for low/high holder cost, zero requests for unattempted candidates, exact budget-bound unknown facts, truthful attempted failures, and blocking missing transport evidence.
- [ ] Run the focused nodes and verify the expected failures.
- [ ] Implement permanent admission using the existing operational candidate maximum and incremental non-throwing pre-attempt decisions.
- [ ] Extend holder results with evaluated/unattempted identities, budget state, before/after ledgers, exact request/transport counts, IDs and coverage.
- [ ] Run the focused nodes and verify they pass.

### Task 3: Observation conversion, freeze, reporting, and replay

**Files:**
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify: `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- Test: `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py`
- Test: `tests/test_v2_9_8b_window_15m_final_integrated_continuous_proof.py`

**Interfaces:**
- Produces: four observation rows from the complete permanent universe, exact `SOURCE_NOT_EVALUATED_BUDGET_BOUND` context, holder attempt budget trace, and replay-stable diagnostics.
- Consumes: extended `HolderContextResult` and unchanged `freeze_eligible_reserve()`.

- [ ] Write focused tests for actual-holder-pass-only `FULLY_ELIGIBLE`, 4→2+2 freeze, <4 coverage blocking, campaign/stage identity reconciliation, and replay identity/count equality.
- [ ] Run the focused nodes and verify the expected failures.
- [ ] Implement observation conversion/report wiring without modifying the freeze owner.
- [ ] Run all new focused tests and nearest affected holder/accounting/freeze suites.

### Task 4: Continuous proof and closeout

**Files:**
- Modify: `tests/test_v2_9_8b_window_15m_final_integrated_continuous_proof.py`
- Create: `docs/printer-v1-v2-9-8b-window-15m-freeze-holder-budget-decoupling-repair-closeout.md`

**Interfaces:**
- Produces: one uninterrupted wrapper-to-memory proof artifact set and factual PASS/BLOCKED closeout.
- Consumes: actual one-shot wrapper, operational child, activation preflight, frozen production transports, Scheduler lifecycle, Lane K, zero-source replay, and disposable Migration-052 database.

- [ ] Run the single continuous proof once with scoped artifact permission and no external network.
- [ ] If it blocks, stop at the exact first blocker and write the BLOCKED closeout without weakening controls.
- [ ] If it passes, run directly affected prior suites and one repository-approved broad closeout regression.
- [ ] Verify authoritative DB hash/integrity/FK/sidecars unchanged and all capability locks show zero deltas.
- [ ] Write closeout with exact identities, counts, per-attempt budgets, execution ID, artifacts/hashes, tests, limitations, and risks.
- [ ] Run diff, compile/import, documentation unlock, and final verification checks.
- [ ] Commit with the factual requested message and push only the repair branch.

# Checkpoint 5 Checkpoint 3 Guard Import-Order Repair Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with strict RED/GREEN verification.

**Goal:** Remove the deterministic discovery-package import cycle while preserving all three accepted Checkpoint 3 contracts and completing the unchanged Checkpoint 5 proof.

**Architecture:** Integrate the two executor guards into their existing owner methods and the request-key helper into its policy module. Remove the package-level eager installer and retire the installer module. Add subprocess import-order coverage so future package initialization changes cannot reintroduce the cycle.

**Tech Stack:** Python 3.12, pytest, SQLite fixture tests, Git.

## Global Constraints

- Solana-only, Solana memecoin-only, paper-only V1.
- No providers, public Printer command, Scheduler/lifecycle runtime, authorization, authoritative DB mutation, memory generation, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, longer-window activation, or Checkpoint 6 work.
- Preserve Source Governor and Central Scheduler ownership.
- Preserve the three accepted Checkpoint 3 contracts exactly.
- Use minimum sufficient risk-based tests.

---

### Task 1: Add import-order regression coverage

**Files:**
- Create: `tests/test_v2_9_8b_checkpoint5_import_order_repair.py`

**Produces:** Independent subprocess imports for four public/internal module entry orders.

- [ ] Write a parametrized subprocess test that starts a fresh interpreter with `PYTHONPATH=src` and imports each module independently.
- [ ] Run it at pre-repair HEAD and verify the `abstract_campaign_command` and authoritative lifecycle orders fail with the circular-import traceback.
- [ ] Commit the RED test only.

### Task 2: Move request-key scope ownership

**Files:**
- Modify: `src/printer_v1/discovery/permanent_discovery_availability.py`
- Test: existing Checkpoint 3 source-scope tests plus Task 1 imports.

**Produces:** `request_key_belongs_to_root(request_key: str, request_key_root: str) -> bool` as a normal module function.

- [ ] Add the exact-root-or-hyphen-child helper without changing callers.
- [ ] Run the exact source-scope tests.

### Task 3: Move direct failure and handoff identity guards into the executor

**Files:**
- Modify: `src/printer_v1/discovery/combined_executor.py`
- Test: existing Checkpoint 3 direct-failure and handoff-identity tests.

**Produces:** Native owner behavior with no monkeypatch installation.

- [ ] Add the direct-provider failure branch at the start of `_run_direct_lane`, preserving request/failure/link/terminal ordering.
- [ ] Add existing-pair token/base-mint validation at the start of `_handoff_one_slot`.
- [ ] Run the exact Checkpoint 3 regressions.

### Task 4: Remove eager package mutation

**Files:**
- Modify: `src/printer_v1/discovery/__init__.py`
- Delete: `src/printer_v1/discovery/checkpoint3_guards.py`
- Test: `tests/test_v2_9_8b_checkpoint5_import_order_repair.py`

**Produces:** Side-effect-free discovery package initialization.

- [ ] Remove the installer import and call from `discovery/__init__.py`.
- [ ] Confirm no repository import references `checkpoint3_guards`.
- [ ] Delete the installer module.
- [ ] Run the import-order test and verify all orders pass.

### Task 5: Focused regression and unchanged Checkpoint 5 proof

**Files:**
- No additional production changes unless a new deterministic defect is proven and separately classified.

- [ ] Run the new import-order test.
- [ ] Run the minimum Checkpoint 3 direct-failure, handoff-identity, and request-scope regressions.
- [ ] Run the unchanged Checkpoint 5 focused Scheduler/lifecycle suite.
- [ ] Run the AST/static contracts, `git diff --check`, and clean-worktree check.
- [ ] If any failure occurs, stop and classify it before changing code.

### Task 6: Closeout

**Files:**
- Create: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation-closeout.md`

- [ ] Record baseline, audit, blocker, design, implementation, exact test results, limitations, money-usefulness contribution, remaining locks, and risks.
- [ ] Verify only intended production/test/docs files changed.
- [ ] Mark `DTW-31` Done only after all proof gates pass.
- [ ] Do not start Checkpoint 6.

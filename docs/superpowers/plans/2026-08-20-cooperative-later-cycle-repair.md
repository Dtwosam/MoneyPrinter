# Cooperative Later-Cycle Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the 4/2/2 factory so an active later-cycle acquisition cannot be abandoned or unnecessarily under-serviced after a cooperative quantum.

**Architecture:** Keep the existing Central Scheduler, Source Governor, lifecycle-deadline guard, and four-token capacity policy unchanged. After a later-cycle boundary returns RUNNING, distinguish immediate cooperative progress from a genuine persisted temporal-refresh wait, then re-enter the canonical coordinator at the earliest lawful wake instead of reusing stale lifecycle selection.

**Tech Stack:** Python 3, SQLite, pytest/unittest, GitHub Actions.

**Spec:** `docs/printer-v1-v2-9-8b-cooperative-later-cycle-repair-design.md`

## Global Constraints

- Solana-only; Solana memecoin-only; paper-only.
- No live wallet, keys, signing, real funds or live execution.
- No paid API dependency.
- No scoring/ranking/confidence/weighted logic.
- No embeddings/vectors.
- No Source Governor or Central Scheduler bypass.
- No dirty-memory retrieval/decision use.
- Retrieval and financial capabilities remain locked.
- 4 total through-4h tokens; 2 active cycles; 2 tokens/cycle; 300s minimum spacing.
- Exact-pool liquidity floor remains `$3,000`.
- Retries remain `0`; endpoint rotation remains `false`.
- No Cycle 3 activation; no 12h/24h activation.
- Offline/disposable proof only; no providers, live Printer run, authorization or authoritative DB mutation.

---

### Task 1: Add regression contract

**Files:**
- Create: `tests/test_v2_9_8b_cooperative_later_cycle_repair.py`
- Create temporarily for proof: `.github/workflows/v2-9-8b-cooperative-later-cycle-repair-proof.yml`

**Interfaces:**
- Consumes: `FourTokenAdmissionBoundaryResult`, `run_one_command_15m_factory`.
- Produces: RED proof that current code lacks the required RUNNING re-evaluation contract.

- [ ] **Step 1: Write the failing tests**

Tests must require:

```python
from printer_v1.operator_cli.one_command_15m_factory import (
    FourTokenAdmissionBoundaryResult,
    _active_later_cycle_refresh_wake_at,
    _cooperative_later_cycle_recheck,
    run_one_command_15m_factory,
)
```

and prove:

```python
# RUNNING with no refresh wait -> immediate recheck.
# RUNNING with refresh wait -> wake at earliest(refresh, lifecycle, proof deadline).
# non-RUNNING -> no recheck.
# multiple/claimed refresh ownership -> fail closed.
# source order places cooperative recheck before `if pending is None:`.
```

- [ ] **Step 2: Run the focused test at the baseline**

Run:

```bash
pytest -q tests/test_v2_9_8b_cooperative_later_cycle_repair.py
```

Expected: FAIL because the new coordination helpers/callsite do not exist yet.

- [ ] **Step 3: Preserve the exact RED evidence**

Record workflow run/job identity and failing assertion/import in the eventual closeout.

---

### Task 2: Implement minimal coordinator repair

**Files:**
- Modify: `src/printer_v1/operator_cli/one_command_15m_factory.py`
- Test: `tests/test_v2_9_8b_cooperative_later_cycle_repair.py`

**Interfaces:**
- Produces: `_active_later_cycle_refresh_wake_at(...)` and `_cooperative_later_cycle_recheck(...)` used by the main factory loop.

- [ ] **Step 1: Resolve active temporal-refresh wake**

Implement a read-only helper using the existing `active_refresh_waits()` ownership rows. It returns `None` for no active wait, returns the parsed `scheduled_for` for exactly one WAITING row, and raises on ambiguous/CLAIMED ownership.

- [ ] **Step 2: Extend boundary result**

Add an optional RUNNING wake timestamp to `FourTokenAdmissionBoundaryResult` without changing existing positional semantics.

- [ ] **Step 3: Bind RUNNING result to persisted wait truth**

When `_run_four_token_admission_boundary()` receives a nonterminal RUNNING attempt, resolve the active temporal wait for that exact campaign/run/later-cycle identity and return it with the boundary result.

- [ ] **Step 4: Add pure coordinator recheck calculation**

Implement a helper that returns:

```python
(False, None)  # non-RUNNING
(True, None)   # RUNNING cooperative quantum -> immediate recheck
(True, earliest_due)  # RUNNING temporal wait -> bounded wake
```

where `earliest_due = min(refresh_due, fresh_next_lifecycle_due, proof_deadline)`.

- [ ] **Step 5: Repair main-loop ordering**

Immediately after the admission-boundary result handling and before any stale `pending is None` branch/sleep, call the recheck helper. Immediate work uses `continue`; delayed work uses existing `_sleep_with_cancellation()` and then `continue`.

Do not change `_later_cycle_acquisition_deadline_conflict()`, terminal validation, cadence, capacity, retries, endpoint rotation, Source Governor or Central Scheduler ownership.

- [ ] **Step 6: Run focused GREEN proof**

Run:

```bash
pytest -q tests/test_v2_9_8b_cooperative_later_cycle_repair.py
```

Expected: PASS.

---

### Task 3: Run directly affected regressions

**Files:**
- No product changes unless a regression identifies an actual compatibility defect.

**Interfaces:**
- Consumes: repaired factory coordinator.
- Produces: bounded regression evidence.

- [ ] **Step 1: Run focused four-token/factory regressions**

Run existing tests that cover the canonical one-command factory, four-token admission integration, later-cycle temporal refresh ownership, and D123 materialization isolation. Prefer exact files discovered in the branch; do not substitute a giant full suite.

- [ ] **Step 2: Run syntax/diff checks**

Run:

```bash
python -m py_compile src/printer_v1/operator_cli/one_command_15m_factory.py

git diff --check 91535856be9e335ede15308c3b422b5e8a4e8bec...HEAD
```

- [ ] **Step 3: Verify locks by diff inspection**

Confirm no changes to capacity policy, provider cadence/rate limits, financial/retrieval activation, 12h/24h, Source Governor bypass, Central Scheduler bypass, retry count or endpoint rotation.

---

### Task 4: Closeout

**Files:**
- Create: `docs/printer-v1-v2-9-8b-cooperative-later-cycle-repair-closeout.md`
- Delete temporary proof workflow before final branch state.

**Interfaces:**
- Produces: auditable lane verdict and exact next permitted action.

- [ ] **Step 1: Read verification evidence fresh**

Do not rely on earlier run output. Re-fetch the final workflow/job/log evidence and final branch diff.

- [ ] **Step 2: Write closeout**

Close only if all focused and affected tests are GREEN. Record baseline, final commit, changed files, RED proof, GREEN proof, invariant checks, and remaining separate blockers.

Expected verdict:

```text
V2_9_8B_COOPERATIVE_LATER_CYCLE_REPAIR_CLOSEOUT_GREEN
```

- [ ] **Step 3: Remove temporary workflow and verify final tree**

Ensure no proof-only workflow remains and no runtime/provider artifacts were created.

- [ ] **Step 4: Final stop condition**

Do not create a fresh operational authorization or run Printer. GoPlus/Solana-native safety redundancy remains a separate lane before another authoritative 4/2/2 campaign unless separately closed.
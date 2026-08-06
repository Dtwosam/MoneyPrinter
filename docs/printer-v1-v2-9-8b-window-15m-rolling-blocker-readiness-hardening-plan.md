# Printer V1 V2-9.8B WINDOW_15M Rolling Blocker-Readiness Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use Superpowers test-driven development and systematic debugging for each confirmed defect. Execute inline in checkpoint order with a fresh review gate between commits.

**Goal:** Audit the complete ordinary public `WINDOW_15M` path in execution order, repair every confirmed deterministic blocker as it is found, and finish with one successful fixture-backed public-composition proof before any new authorization is considered.

**Architecture:** The work is split into sequential checkpoints that mirror the real public call path. Every checkpoint begins from the prior clean commit, produces an audit record even when no defect is found, and permits production changes only after a reachable RED reproduction. A final disposable proof enters through the real public composition and verifies clean-memory closeout, terminal propagation, cleanup, and lock preservation.

**Tech stack:** Python 3.12, pytest, SQLite disposable migrated databases, PowerShell wrapper contract inspection, GitHub Actions for offline proof, GitHub commits/branches, Linear tracking.

## Global constraints

- Baseline commit: `50de72cc06a3f2597b3a56e660e3728128d1e2d1`.
- Active lane: `V2-9.8B — Active Bounded Memory Growth Operations`.
- No authorization, application marker, wrapper application, public operational command, provider request, discovery runtime, holder runtime, Scheduler runtime, lifecycle runtime, or memory runtime.
- No authoritative DB mutation, restore, vacuum, checkpoint, normalization, or replacement.
- Solana-only, Solana memecoin-only, paper-only.
- No Source Governor or Central Scheduler bypass.
- `WINDOW_5M_MICRO_EVENT` remains support-only.
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` remain locked.
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, real funds, paid APIs, scoring, ranking, confidence, weighting, embeddings, and vectors remain locked.
- Tests use fixture transports and disposable migrated databases only.
- Use risk-based minimum sufficient tests at each checkpoint; broad proof only at Checkpoint 8.

---

### Task 0: Adopt the rolling hardening control documents

**Files:**
- Create: `docs/printer-v1-v2-9-8b-window-15m-rolling-blocker-readiness-hardening-design.md`
- Create: `docs/printer-v1-v2-9-8b-window-15m-rolling-blocker-readiness-hardening-plan.md`

**Interfaces:**
- Consumes: active Printer V1 source stack and closeout commit `50de72cc...`.
- Produces: checkpoint order, finding classifications, test policy, and hard locks used by every later task.

- [x] Commit the approved design.
- [x] Commit this executable plan.
- [ ] Verify the design branch descends exactly from `50de72cc...` and contains documentation changes only.
- [ ] Mark Linear `DTW-26` complete and start `DTW-27`.

Verification:

```bash
git merge-base --is-ancestor 50de72cc06a3f2597b3a56e660e3728128d1e2d1 HEAD
git diff --check 50de72cc06a3f2597b3a56e660e3728128d1e2d1..HEAD
git diff --name-only 50de72cc06a3f2597b3a56e660e3728128d1e2d1..HEAD
```

Expected: only the two control documents differ.

---

### Task 1: Audit and harden wrapper-to-child terminal propagation

**Files:**
- Inspect/modify: `src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py`
- Inspect/modify: `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- Inspect/modify: `src/printer_v1/operator_cli/unified_terminal_closure.py`
- Create if needed: `src/printer_v1/operator_cli/window_15m_child_terminal.py`
- Inspect: `scripts/Start-PrinterV1-Window15M-OneShot.ps1`
- Modify/create tests: `tests/test_v2_9_8b_window_15m_one_shot_wrapper.py`
- Modify/create tests: `tests/test_v2_9_8b_operational_memory_factory_command.py`
- Create checkpoint tests: `tests/test_v2_9_8b_window_15m_child_terminal_propagation.py`
- Create closeout: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-1-terminal-propagation-closeout.md`

**Interfaces:**
- Consumes: wrapper child command and existing campaign terminal reporting.
- Produces: a bounded child terminal envelope and wrapper projection with exact first cause, phase, identities, cleanup state, active residue, DB identity, and report identity.

- [ ] Map all wrapper outcomes: pre-marker block, consumed/no-child, process-start failure, child zero, child nonzero.
- [ ] Map all operational-command success and handled-exception exits.
- [ ] Write RED tests showing a nonzero child with a valid terminal envelope currently collapses to `CHILD_EXITED_NONZERO` and loses the structured cause.
- [ ] Write RED tests for malformed, missing, oversized, or unsafe child terminal envelope input.
- [ ] Add one canonical child-envelope schema and create-once writer owned by the child.
- [ ] Ensure handled child failures write the envelope only after cleanup/reconciliation is complete.
- [ ] Add wrapper read/validate/project behavior after child exit without parsing arbitrary stderr.
- [ ] Keep launch/bootstrap failures distinct when no child envelope can lawfully exist.
- [ ] Preserve stdout/stderr hashes and immutable evidence.
- [ ] Run focused tests:

```bash
python -m pytest \
  tests/test_v2_9_8b_window_15m_child_terminal_propagation.py \
  tests/test_v2_9_8b_window_15m_one_shot_wrapper.py \
  tests/test_v2_9_8b_operational_memory_factory_command.py \
  -q
python -m py_compile \
  src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py \
  src/printer_v1/operator_cli/window_15m_child_terminal.py \
  src/printer_v1/operator_cli/operational_memory_factory_command.py \
  src/printer_v1/operator_cli/unified_terminal_closure.py
git diff --check
```

- [ ] Independently inspect source-safety, no-retry semantics, and failure precedence.
- [ ] Commit checkpoint closeout and update Linear `DTW-27`.

Stop condition: implementation would require changing campaign semantics, retry policy, source policy, DB schema, or authorization behavior rather than reporting ownership.

---

### Task 2: Audit child preflight and campaign initialization

**Files:**
- Inspect/modify: `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- Inspect/modify: `src/printer_v1/operator_cli/window_15m_concrete_composition.py`
- Inspect/modify: `src/printer_v1/operator_cli/git_provenance_authorization_manifest.py`
- Inspect/modify: `src/printer_v1/operator_cli/pre_authorization_migration_ledger_guard.py`
- Inspect/modify: `src/printer_v1/operator_cli/campaign_persistence.py`
- Inspect/modify: `src/printer_v1/operator_cli/campaign_ownership.py`
- Inspect/modify: `src/printer_v1/operator_cli/campaign_supervision.py`
- Inspect/modify: `src/printer_v1/operator_cli/operational_campaign_recovery.py`
- Test: nearest preflight, provenance, migration-ledger, ownership, supervision, and recovery suites.
- Create closeout: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-2-preflight-initialization-closeout.md`

**Interfaces:**
- Consumes: validated child environment and wrapper binding artifacts.
- Produces: zero-source readiness or one precise preflight classification before source work; clean campaign/run/cycle/supervision initialization after readiness.

- [ ] Trace every preflight gate and side effect ordering.
- [ ] Prove any suspected defect with a disposable DB or filesystem fixture.
- [ ] Add RED regression for each confirmed defect.
- [ ] Implement minimal repair and focused tests.
- [ ] Verify no campaign identity, artifact, lease, heartbeat, or DB mutation occurs before all zero-source gates pass.
- [ ] Verify post-initialization failures preserve cleanup ownership and exact terminal phase.
- [ ] Commit checkpoint closeout and update Linear `DTW-28`.

---

### Task 3: Audit discovery, selection, source scope, and accounting

**Files:**
- Inspect/modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Inspect/modify: `src/printer_v1/discovery/permanent_discovery_availability.py`
- Inspect/modify: `src/printer_v1/discovery/direct_migration_discovery.py`
- Inspect/modify: `src/printer_v1/discovery/eligible_token_supply.py`
- Inspect/modify: `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- Inspect/modify: `src/printer_v1/sources/campaign_six_unit_accounting.py`
- Inspect/modify: `src/printer_v1/sources/measured_transport.py`
- Inspect/modify: discovery Scheduler claim/work ownership modules reached by the public path.
- Test: source scope, temporal authority, transport identity, manifest, Scheduler claim, two-slot handoff, and cleanup suites.
- Create closeout: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-3-discovery-accounting-closeout.md`

**Interfaces:**
- Consumes: initialized campaign ownership and fixture source transports.
- Produces: exact two-slot discovery/selection evidence or one honest source/live-condition block, with exact request and transport reconciliation.

- [ ] Trace the exact public discovery composition and every producer collected by the campaign manifest.
- [ ] Re-run permanent regressions for all prior consumed-authorization defects.
- [ ] Prove and repair any new deterministic defect one at a time.
- [ ] Verify provider failures remain distinct from accounting, temporal, scope, and identity defects.
- [ ] Verify safe-stop cleanup releases Scheduler/discovery work.
- [ ] Commit checkpoint closeout and update Linear `DTW-29`.

---

### Task 4: Audit holder budget, evidence, and two-token admission

**Files:**
- Inspect/modify: `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
- Inspect/modify: holder source execution, persistence, maturation, and eligibility modules reached by `authoritative_live_operational_campaign.py`.
- Inspect/modify: campaign operation-ledger and admission reservation owners.
- Test: exact `M = C = A`, budget, pacing, holder response/failure, maturation, eligibility, admission, and cleanup suites.
- Create closeout: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-4-holder-admission-closeout.md`

**Interfaces:**
- Consumes: exact reconciled discovery source truth and two-slot candidate supply.
- Produces: two holder-eligible admitted tokens or one exact expected live-condition/deterministic blocker.

- [ ] Trace every count, identity, reservation, and persistence surface.
- [ ] Verify the action-local and campaign owners remain independent.
- [ ] Prove/repair any deterministic defect without changing holder eligibility policy or provider order.
- [ ] Verify no holder transport occurs after a pre-holder defect.
- [ ] Commit checkpoint closeout and update Linear `DTW-30`.

---

### Task 5: Audit Scheduler ownership and lifecycle activation

**Files:**
- Inspect/modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Inspect/modify: `src/printer_v1/scheduler/scheduler.py`
- Inspect/modify: campaign Scheduler-work ownership modules.
- Inspect/modify: lifecycle activation/orchestration modules reached by the public campaign.
- Inspect/modify: `src/printer_v1/discovery/memory_observation_activation.py`
- Test: Scheduler claim-at-work-start, work identity, token-slot linkage, lifecycle creation, cancellation, lease renewal, and support-only 5m suites.
- Create closeout: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-5-scheduler-lifecycle-closeout.md`

**Interfaces:**
- Consumes: exact admitted token slots.
- Produces: Scheduler-owned lifecycle work for the main `WINDOW_15M` only, with conditional exact-linked support 5m evidence.

- [ ] Trace all work creation/claim/release orderings.
- [ ] Prove/repair deterministic ownership or lifecycle activation defects.
- [ ] Verify no direct runtime bypasses Central Scheduler.
- [ ] Verify 5m cannot independently promote memory or continuation.
- [ ] Commit checkpoint closeout and update Linear `DTW-31`.

---

### Task 6: Audit WINDOW_15M collection and clean-memory closeout

**Files:**
- Inspect/modify: main 15m lifecycle collector and observation modules reached by the public campaign.
- Inspect/modify: snapshot coverage/gap audit owners.
- Inspect/modify: episode, outcome, clean-memory, fingerprint, and audit owners.
- Inspect/modify: final campaign report projections of memory results.
- Test: exact token/pair continuity, freshness, quality, gap, 5m exclusion, episode/outcome, clean/dirty/blocked, fingerprint, and anti-look-ahead suites.
- Create closeout: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-6-memory-closeout.md`

**Interfaces:**
- Consumes: Scheduler-owned exact token/pair lifecycle evidence.
- Produces: one honest clean, dirty, or blocked `WINDOW_15M` closeout per admitted slot; clean memory only when all gates pass.

- [ ] Trace every state transition and write boundary.
- [ ] Prove/repair deterministic collection or closeout defects without weakening cleanliness gates.
- [ ] Verify no dirty or 5m evidence enters main memory or retrieval/decision surfaces.
- [ ] Verify positive and negative outcomes can remain clean when evidence is complete.
- [ ] Commit checkpoint closeout and update Linear `DTW-32`.

---

### Task 7: Audit terminal closure, cleanup, replay, and residue

**Files:**
- Inspect/modify: `src/printer_v1/operator_cli/unified_terminal_closure.py`
- Inspect/modify: `src/printer_v1/operator_cli/final_campaign_report.py`
- Inspect/modify: `src/printer_v1/operator_cli/campaign_supervision.py`
- Inspect/modify: `src/printer_v1/operator_cli/operational_campaign_recovery.py`
- Inspect/modify: Scheduler/discovery/factory cleanup owners reached by terminal closure.
- Test: success/failure closure, first-cause precedence, report immutability, report-only replay, lease/lock/work release, and zero-residue suites.
- Create closeout: `docs/printer-v1-v2-9-8b-window-15m-checkpoint-7-terminal-cleanup-closeout.md`

**Interfaces:**
- Consumes: campaign result or exception plus all reached identities.
- Produces: one immutable terminal report/envelope, complete cleanup, and zero active residue without retry/restart/successor creation.

- [ ] Exercise failures before and after each major ownership boundary.
- [ ] Prove/repair cleanup or first-cause reporting defects.
- [ ] Verify replay is read-only/idempotent and cannot create campaign or financial rows.
- [ ] Commit checkpoint closeout and update Linear `DTW-33`.

---

### Task 8: Run full disposable public-composition proof and final closeout

**Files:**
- Create: `tests/test_v2_9_8b_window_15m_full_disposable_public_composition.py`
- Create if needed: a fixture-only test support module under `tests/support/`.
- Create: `docs/printer-v1-v2-9-8b-window-15m-rolling-blocker-readiness-hardening-closeout.md`

**Interfaces:**
- Consumes: all checkpoint commits.
- Produces: one complete fixture-backed ordinary `WINDOW_15M` clean-memory closeout plus representative fail-closed proof and final readiness verdict.

- [ ] Enter through the same public child composition used by ordinary `run`, with fixture-injected transports and a disposable migrated DB.
- [ ] Prove two-token discovery/admission, Scheduler ownership, 15m collection, clean-memory closeout, terminal envelope, wrapper projection contract, cleanup, and zero residue.
- [ ] Prove representative pre-marker, preflight, discovery, holder, lifecycle, memory, and cleanup failures remain distinct and fail closed.
- [ ] Verify zero retrieval/decision/position/trade/audit/PnL deltas.
- [ ] Run the final risk-based combined suites and compilation/diff checks.
- [ ] Independently inspect the final branch against this plan and the active source stack.
- [ ] Record money-usefulness, remaining live-condition uncertainty, and exact next step.
- [ ] Mark Linear `DTW-34` and parent `DTW-25` complete only on PASS.

Final PASS requires:

```text
all reached deterministic boundaries audited
all confirmed defects repaired with RED regressions
complete disposable public composition PASS
exact child-to-wrapper terminal propagation PASS
cleanup and zero active residue PASS
all V1 locks preserved
no authorization/provider/runtime execution
```

A PASS does not authorize another live run. Any future authorization remains a separate operator-approved lane.

# Printer V1 V2-9.8B WINDOW_15M Checkpoint 5 — Scheduler Ownership and Lifecycle Activation Audit

## Audit status

`V2_9_8B_WINDOW_15M_CHECKPOINT_5_SCHEDULER_LIFECYCLE_AUDIT_NO_REACHABLE_DEFECT_FOUND_PENDING_FOCUSED_PROOF`

This is an audit/readiness result, not the final checkpoint verdict.

- Baseline: `421e409628a0db443f1c417835a9d5b06bbdc834`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-5-scheduler-ownership-lifecycle-activation`
- Linear: `DTW-31`
- Mode: static inspection and existing-artifact review only
- Scheduler/lifecycle runtime: not run
- Provider/source access: none
- Authorization: none created, reused, modified, or consumed
- Authoritative database: not accessed or mutated

Checkpoint 6 is not started.

## Controlling source stack

This audit used the active Printer V1 source stack together:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

It also reviewed the accepted V2-9.7E lifecycle/cleanup repair, V2-9.8B Scheduler-ownership correction, C1-C15 full-run accounting implementation, and SQLite heartbeat-concurrency closeout.

## Exact ordinary path inspected

```text
two memory-admitted token slots
→ immutable selected-item / first-15m Scheduler job lineage
→ superseded executor first-15m jobs cancelled through Central Scheduler
→ identity-preserving two-item factory selection batch
→ preallocated factory run and immutable campaign/run/cycle/configuration identity
→ Central Scheduler enqueue
→ Central Scheduler claim
→ bounded WINDOW_15M snapshots and close
→ conditional same-stream support-only 5m capture
→ main WINDOW_15M campaign-window registration
→ Central Scheduler terminal state
→ token-local failure isolation or global safe stop
→ campaign-scoped terminal cleanup
→ zero active/locked owned work
→ lease release
→ no retry, resume, restart, or successor
```

Primary owners inspected:

- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/campaign_ownership.py`
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/campaign_active_work.py`
- `src/printer_v1/operator_cli/campaign_supervision.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `src/printer_v1/scheduler/scheduler.py`
- `src/printer_v1/sources/campaign_six_unit_accounting.py`
- `src/printer_v1/sources/measured_transport.py`

## Boundary findings

### 1. Admitted two-token handoff

Classification: `NO_REACHABLE_DEFECT_FOUND`.

The lifecycle bridge reads exactly two atomically activated `SELECTED` slots, requires distinct token identities and ordinals 1 and 2, and materializes one two-item `WINDOW_15M` selection batch without rediscovery or reselection.

The executor-created first-15m jobs are superseded by the factory schedule and are cancelled through the canonical Scheduler owner before factory planning. Their exact identities remain recoverable through the immutable selected-item link.

Post-handoff fault handling records exact campaign/run/cycle/factory/batch/token/pair/job/step/snapshot/window/lease ownership and compensates only that scope. Historical or unrelated rows and leases are not eligible for deletion.

### 2. Central Scheduler mutation ownership

Classification: `NO_REACHABLE_DEFECT_FOUND`.

One Scheduler module owns the mutation boundaries:

- `enqueue_job()` emits `SCHEDULER_ENQUEUE` after the durable job insert;
- `claim_due_job()` emits `SCHEDULER_CLAIM` after the job becomes `RUNNING` and gains its lock;
- `complete_job()`, `fail_job()`, and `cancel_job()` emit `SCHEDULER_TERMINAL` from the actual terminal mutation.

The operational lifecycle does not infer claim or terminal state from a caller-supplied value. Campaign ownership projection reads the canonical Scheduler job or durable Scheduler evidence and validates exact lineage, target category, target identity, scope, stage, factory run, and campaign/run/cycle ownership.

The approved scopes remain:

- `DISCOVERY_SELECTION`
- `FIRST_15M_HANDOFF`
- `WINDOW_LIFECYCLE`
- `TERMINAL_CLEANUP`

One Scheduler job may belong to one campaign ownership row and one stage only.

### 3. Immutable lifecycle identity and main-window registration

Classification: `NO_REACHABLE_DEFECT_FOUND`.

The factory run ID is preallocated and bound to the campaign run before lifecycle work. The factory receives campaign, campaign run, cycle, configuration, factory run, expected `WINDOW_15M`, and token capacity 2 as one immutable context.

A successful main close registers the exact campaign window before Scheduler and slot terminalization. Registration proves factory step, token, pair, slot, cycle, window kind, memory-window row, and root lifecycle identity. Conflicting ownership fails closed; exact replay is idempotent.

`WINDOW_15M` remains the only accepted top-level factory window kind for this checkpoint.

### 4. Support-only 5m boundary

Classification: `NO_REACHABLE_DEFECT_FOUND`.

The 5m path is conditional and derived from the same run's governed 15m snapshot stream. It is stored as a `SUPPORT_5M` run step and its memory row remains `WINDOW_5M_MICRO_EVENT` / support-only.

It does not replace the main 15m close, satisfy main-window completion, or independently authorize continuation. In natural two-token mode the first close schedules neither support capture nor continuation; both wait for the two-terminal-15m barrier. After the barrier, each token is evaluated from its own governed 15m evidence.

A lawful no-capture disposition remains valid. Missing optional support-only 5m evidence cannot dirty an otherwise valid main 15m memory.

### 5. Failure, cancellation, and retry prevention

Classification: `NO_REACHABLE_DEFECT_FOUND`.

Although the generic Scheduler `fail_job()` supports cooldown retries for other historical uses, every operational lifecycle failure call passes `max_retries=0`.

Therefore:

- a blocked or unexpected token-local step becomes terminal `FAILED` immediately;
- remaining pending work for that token is cancelled;
- a global budget/integrity stop terminalizes the active job and invokes run-wide cleanup;
- no operational failure enters Scheduler `COOLDOWN` as an automatic retry;
- no replacement run, resume, restart, or successor is created.

Cancellation probes run before and after intentional waits and governed work. A cooperative cancellation preserves the first reason and disallows new child work.

### 6. Lease renewal and heartbeat ownership

Classification: `NO_REACHABLE_DEFECT_FOUND`.

The campaign supervision owner requires monotonic heartbeat and expiry advancement under exact lease identity. Source execution and pacing release shared write transactions before I/O or sleep, allowing bounded heartbeat renewal without weakening genuine lock handling.

An unconfirmed renewal:

- persists sanitized first-failure evidence when possible;
- performs no cleanup from the heartbeat path;
- sets `new_child_work_allowed=false`;
- signals the main terminal coordinator;
- preserves a typed suggested terminal cause.

Only the main terminal coordinator owns cleanup, first-cause preservation, lease release, and report persistence.

### 7. Terminal cleanup and zero-residue proof surface

Classification: `NO_REACHABLE_DEFECT_FOUND`.

Terminal cleanup captures campaign-scoped active Scheduler jobs before cancellation, then transactionally:

- terminalizes campaign-owned Scheduler work;
- terminalizes active discovery work and batches;
- cancels active or locked Scheduler jobs;
- emits cleanup-owned terminal observations;
- cancels active campaign windows;
- terminalizes cycle, run, campaign, and supervision;
- verifies zero active or locked campaign work;
- releases the exact lease;
- returns durable cleanup and release timestamps.

Idempotent replay preserves the original terminal status and first cause.

The returned contract explicitly records:

- `automatic_retries=0`
- `resume_created=false`
- `successor_created=false`
- `restart_created=false`
- `new_child_work_allowed=false`

### 8. Existing proof coverage

Classification: `READY_FOR_FOCUSED_CURRENT-BRANCH_PROOF`.

Existing disposable tests cover:

- real two-token factory wiring to two terminal `WINDOW_15M` closes;
- discovery, selection, handoff, lifecycle, and cleanup Scheduler ownership;
- enqueue/claim/terminal observation;
- exact campaign-window registration and conflict handling;
- failed, nonterminal, locked, and retried Scheduler state blocking;
- post-handoff fault compensation across all six committed fault points;
- lease acquisition, renewal, genuine lock failure, ownership mismatch, cleanup, and release;
- support-only 5m and two-terminal-close behavior;
- zero active work and no restart/successor.

A fresh focused proof remains required because static inspection and historical PASS reports are not completion evidence for the current branch.

## Rejected suspicions

1. **The factory may automatically retry a failed lifecycle job.** Rejected: every active lifecycle `fail_job()` call passes `max_retries=0`.
2. **Support-only 5m can become the main lifecycle.** Rejected: factory preflight accepts only `WINDOW_15M`; 5m is a conditional support step derived from the same stream.
3. **The first 15m close can independently schedule continuation.** Rejected for natural two-token mode: the peer-close barrier schedules nothing until both closes exist.
4. **Scheduler state is caller-declared.** Rejected: projection derives current state and terminal evidence from canonical Scheduler rows or durable Scheduler evidence.
5. **Heartbeat failure performs competing cleanup.** Rejected: renewal failure only records/surfaces evidence; the main coordinator remains the sole cleanup owner.
6. **Terminal cleanup can leave active/locked owned work while reporting success.** Rejected: cleanup and acceptance explicitly query and block on active/locked residue.
7. **Terminal failure can create a successor or restart.** Rejected: no such creation path exists in the inspected lifecycle, and cleanup returns explicit false values.

## Focused proof required before closeout

Minimum sufficient proof:

1. Python syntax/import checks for the Scheduler, lifecycle, ownership, supervision, cleanup, and accounting owners.
2. Current-branch disposable regressions covering:
   - full-run wiring and exact Scheduler ownership;
   - Scheduler fail/nonterminal/locked/retried blockers;
   - post-handoff compensation and terminal cleanup;
   - heartbeat concurrency and lease failure;
   - support-only 5m and lifecycle/clean-memory separation.
3. A small current-contract probe proving all operational lifecycle `fail_job()` calls retain `max_retries=0` and that cleanup reports no retry/resume/restart/successor.
4. `git diff --check` and a clean disposable worktree.

The proof must use fixture transports and disposable databases only. It must not run the public operational command, providers, authoritative Scheduler/lifecycle runtime, authorization, authoritative DB, or memory-growth campaign.

If a current-contract regression fails, classify the failure before any design or production change. If the focused proof passes, Checkpoint 5 may close without production modification.

## Money-usefulness contribution

Checkpoint 5 protects future paper-only memory growth from duplicated jobs, missing claims, unowned lifecycle work, optional 5m evidence masquerading as a main outcome, hidden retries, abandoned locks, and silent successor runs. This makes future clean 15m evidence more trustworthy without producing a trade signal or financial action.

## What this checkpoint improves

- consolidated current-path confidence in Central Scheduler ownership;
- exact two-token handoff-to-lifecycle identity continuity;
- explicit support-only 5m separation;
- fail-closed no-retry lifecycle behavior;
- lease and terminal cleanup ownership clarity;
- focused proof gate before source collection and clean-memory closeout review.

## What this checkpoint does not unlock

This checkpoint does not unlock or run:

- providers, Printer, or public one-command runtime;
- authorization creation or consumption;
- authoritative database mutation;
- authoritative Scheduler or lifecycle execution;
- memory generation or retrieval;
- paper BUY/SELL/HOLD decisions;
- positions, trade events, paper trade audits, or PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- Checkpoint 6.

All Solana-only, Solana-memecoin-only, paper-only, Source Governor, Central Scheduler, no-paid-API, no-scoring/ranking/confidence/weighting, no-wallet, no-key, and no-real-funds locks remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- Static inspection cannot prove live provider availability, wall-clock cadence, or authoritative production lease behavior.
- The generic Scheduler remains retry-capable for other callers; future operational code must continue to pass zero retries explicitly and the acceptance gate must continue blocking any retry count.
- Migration 050 and stage-scoped ownership have disposable proof history, but this checkpoint does not apply a migration or authorize authoritative runtime.
- Support-only 5m has extensive historical coverage, but the focused proof must use current tests rather than rely on old counts alone.
- The connected GitHub environment cannot execute the local Python suite, so the focused proof must run in a detached disposable worktree on the operator machine.

## Next boundary

Do not begin Checkpoint 6 until the focused Checkpoint 5 proof passes and this checkpoint receives a closeout verdict.
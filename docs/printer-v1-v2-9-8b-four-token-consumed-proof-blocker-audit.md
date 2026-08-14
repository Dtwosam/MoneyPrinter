# Printer V1 V2-9.8B Four-Token Consumed-Proof Blocker Audit

Date: 2026-08-14

Baseline: `d66dc3d9aacf79c4daa09b01dc9a7cf8cdaee91d`

Consumed authorization: `V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260814T101513Z`

Authorization SHA-256: `ddf6521e44243c5a7de073dac75588666bb304294e3e62fc5db5e18c3e6a041c`

Verdict:

`V2_9_8B_FOUR_TOKEN_CONSUMED_PROOF_BLOCKER_AUDIT_PASS_READY_FOR_REPAIR_DESIGN`

## Boundary

Audit/readiness only. The consumed authorization remains permanently consumed. This audit does not authorize, rerun, resume, restart, or replace the proof; run Printer; fetch sources; mutate the authoritative DB; generate memory; or unlock retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Consumed-attempt safety state

The failed attempt closed safely:

- campaign, campaign run, and admitted cycle are terminal;
- zero active campaign cycles;
- zero active campaign Scheduler work;
- zero active Scheduler jobs;
- lease released;
- SQLite integrity `ok`;
- no DB sidecars;
- no retry/rerun/restart/successor was created by the forensic inspection.

The proof therefore has implementation blockers, not an orphaned-runtime or cleanup blocker.

## Finding A — cycle terminal reconciliation rejects valid stage-scoped ownership

`reconcile_four_token_cycle_terminal()` reads every campaign Scheduler ownership row for the cycle and currently requires every row to have:

- `ownership_contract_version == V2_STAGE_SCOPED`;
- `work_scope == WINDOW_LIFECYCLE`;
- a non-null Scheduler job ID.

That scope condition conflicts with the adopted campaign Scheduler ownership design, whose canonical V2 scopes are:

- `DISCOVERY_SELECTION`;
- `FIRST_15M_HANDOFF`;
- `WINDOW_LIFECYCLE`;
- `TERMINAL_CLEANUP`.

The consumed cycle durably contained valid `DISCOVERY_SELECTION`, `FIRST_15M_HANDOFF`, and `WINDOW_LIFECYCLE` rows. Requiring all of them to be `WINDOW_LIFECYCLE` therefore creates a false-positive terminal reconciliation failure:

`cycle terminal reconciliation found non-canonical lifecycle ownership`

Classification: **proven implementation defect**.

Required repair direction: preserve `V2_STAGE_SCOPED`, non-null Scheduler-job ownership, and the exact canonical scope allowlist; do not reinterpret legitimate discovery/handoff work as lifecycle work and do not permit arbitrary scopes.

## Finding B — pre-admission callback holds a write transaction across later-cycle supply

The cycle-2 callback correctly creates the scheduled pre-admission attempt in an atomic transaction and that owner commits before returning. It then claims the Scheduler job and marks the attempt `RUNNING` on the outer operational connection.

Those two writes open a new SQLite transaction. The callback invokes `supply_owner(...)` without committing/releasing that transaction first.

This violates the adopted operational SQLite law in `sqlite_write_contracts.py`: a write transaction must never remain open across source I/O, pacing, waits, or lengthy computation.

The production later-cycle supply runs the canonical permanent graduated-supply pipeline and opens additional operational DB connections/writes. The current boundary is therefore lock-prone by construction.

Classification: **proven implementation defect**.

Required repair direction: after the Scheduler claim and `RUNNING` transition are durably committed, release the outer write transaction before invoking the supply owner. Re-establish a short write boundary only when persisting returned evidence/pair/terminal state. Do not change discovery eligibility, exact-two policy, source budgets, Scheduler ownership, Source Governor ownership, or retry policy.

## Finding C — generic exception terminal destroys cycle-2 root-cause provenance

The callback already has an honest `NO_PAIR` path. When the canonical supply returns fewer than exactly two candidates, it terminalizes the attempt as `NO_PAIR` with `supply.terminal_cause` (or `NO_EXACT_PAIR`). Therefore an ordinary supply shortage is not represented as `LATER_CYCLE_SUPPLY_FAILED`.

`LATER_CYCLE_SUPPLY_FAILED` is written only by the broad exception handler. That handler discards the underlying exception type/code/detail before persisting the attempt and Scheduler terminal.

The consumed attempt therefore proves that an exception occurred, but its exact thrown exception is not recoverable from the durable pre-admission attempt row. The open-transaction defect above is a proven invalid boundary and is consistent with the observed failure, but the swallowed exception prevents claiming the exact thrown SQLite/error identity from the durable record alone.

Classification: **proven diagnostic/provenance defect**.

Required repair direction: preserve a bounded typed underlying terminal cause for the failed pre-admission attempt and Scheduler job. Do not persist secrets, raw response bodies, stack traces, arbitrary exception text, or provider payloads. Expected known domain errors should retain their stable code; unknown exceptions should retain at least a stable exception class/category while the public proof terminal remains fail-closed.

## Finding D — `retry_count = 1` did not mean one retry

The consumed pre-admission Scheduler job had `retry_count = 1`, but its failure path called `fail_job(..., max_retries=0)`.

Scheduler `fail_job()` increments `retry_count` for the failed execution before evaluating retry eligibility. With `max_retries=0`, the job transitions directly to `FAILED`; it is not placed into `COOLDOWN` and is not requeued.

Classification: **not a blocker**. The frozen no-retry contract was preserved.

## Repair scope

The next lane must be design/specification only and must cover exactly:

1. stage-scope-aware cycle terminal reconciliation;
2. pre-admission transaction release before later-cycle supply;
3. bounded typed preservation of the underlying later-cycle exception terminal.

No repair is authorized to:

- widen the two-token-per-cycle or four-token proof contract;
- retry, rotate, or source-fetch outside existing budgets;
- relax exact-two candidate admission;
- convert an honest no-pair result into success;
- bypass Source Governor or Central Scheduler;
- change public/default `TOKEN_CAPACITY == 2`;
- activate 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Minimum proof before closeout

Implementation, if later approved by design, must use focused TDD and minimum sufficient checks:

- RED: valid mixed canonical V2 stage scopes reproduce the false-positive reconciliation failure; GREEN: canonical mixed scopes pass while unknown scopes, wrong ownership version, missing Scheduler job, active/orphan work still fail closed;
- RED: later-cycle supply is invoked while the pre-admission connection is still in a write transaction; GREEN: supply is invoked only after that transaction is released, while Scheduler claim and `RUNNING` state remain durable;
- RED/GREEN: honest no-pair retains its canonical supply terminal and remains `NO_PAIR`;
- RED/GREEN: known later-cycle domain exceptions persist a bounded stable cause; unknown exceptions remain fail-closed without sensitive/raw payload persistence;
- lock/no-retry assertions remain unchanged;
- focused py_compile/diff checks and directly affected tests only. Broad suites are reserved for repair closeout/pre-proof validation.

No live proof or fresh authorization belongs in the implementation test lane.

## Money-usefulness contribution

This repair protects useful memory growth by making the four-token capacity proof measure actual multi-cycle behavior rather than fail on a false ownership validator or a self-created SQLite lock. Better terminal provenance also prevents repeated paid-in-time operator attempts against an unknown blocker.

## What this improves

- truthful stage-scoped Scheduler ownership reconciliation;
- safe SQLite transaction boundaries for cycle-2 discovery/selection;
- actionable terminal provenance when cycle-2 composition genuinely faults.

## What this still does not unlock

It does not prove four-token memory growth, create a new authorization, permit a rerun, or unlock any later memory/retrieval/trading capability.

## Functionality Risks / Setbacks / Efficiency Blockers

- The consumed exception's exact original class/message was not durably preserved; repair must not invent it retrospectively.
- Releasing the write transaction must not release Scheduler ownership: the durable `RUNNING` attempt and claimed Scheduler job remain the authority while source work executes.
- Exception provenance must be bounded and stable; raw arbitrary exception text can leak provider payloads or create nondeterministic terminals.
- Terminal reconciliation must not fix the false positive by simply ignoring non-window work; all canonical campaign-owned Scheduler scopes still require valid V2 ownership and terminal cleanup.

## Next permitted lane

`V2-9.8B FOUR-TOKEN CONSUMED-PROOF BLOCKER REPAIR DESIGN`

Design these three repairs only. Do not prepare a fresh authorization or run another four-token proof until design, TDD implementation, bounded verification, closeout, and independent rereview all pass.
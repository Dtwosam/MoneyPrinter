# Printer V1 V2-9.8B — Historical Execution Reconciliation Audit & Design

## Verdict

`V2_9_8B_HISTORICAL_EXECUTION_RECONCILIATION_AUDIT_DESIGN_PASS_READY_FOR_FOCUSED_TDD`

## Lane identity

- Starting repair closeout: `1b5a8cdf0dad74b8fa4730d090abfc8d6cd184a1`
- Historical execution: `20260814T172224Z-490856f405bf`
- Historical factory run: `ed0fa279-38e6-401b-8b34-0a9531a9c720`
- Preserved pre-reconciliation DB SHA: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`
- Historical schema head: `055_pre_admission_discovery_attempt_ownership.sql`
- Branch: `agent/v2-9-8b-historical-execution-reconciliation`

This lane does not authorize a fresh Printer run or any financial/retrieval capability.

## Local evidence binding

The Mac-local read-only evidence pass returned `LOCAL_HISTORICAL_RECONCILIATION_EVIDENCE_PASS` and re-proved:

- authoritative DB SHA is unchanged and exact;
- migration count/head remain 55 / migration 055;
- integrity is `ok`, FK violations are zero, and no SQLite sidecars exist;
- campaign/run/Cycle 1/supervision/factory remain `RUNNING/RUNNING/PLANNED/ACTIVE/RUNNING`;
- zero campaign windows, zero factory steps, zero Cycle-2 attempts, zero active discovery work, zero active Scheduler jobs, zero proof supervision;
- ten campaign Scheduler-work rows remain terminal/canonical and jobs 2011–2020 remain terminal/unlocked;
- historical PID 59354 is dead, no Printer process references the execution, no process holds the DB or lease lock;
- the lease is expired and its on-disk payload exactly matches campaign/run/supervision/configuration/owner identity;
- all required historical artifacts exist with stable SHA256 evidence;
- the artifacts support `FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction` as the earliest recorded controlling cause and name no earlier cause;
- migration-056 provenance is absent, as required.

The artifacts also record downstream closure failures `cleanup:OperationalError:database is locked` and `reconciliation:OperationalError:database is locked`, consistent with the unreleased transaction that prevented terminal closeout.

## Historical slot and tracking-queue evidence

Cycle-1 slot order remains:

1. `yUmeQo96g6MurikjHiMg7u23X5yQXJ9SQpoJPcbpump` — slot state `SELECTED`, tracking queue id `58`.
2. `CAGtwKrcnwgLABdg5o16oMczxUV6i1pj973K9XWQpump` — slot state `SELECTED`, tracking queue id `59`.

Both linked `printer_tracking_queue` rows are still non-terminal:

- lane `TRACK_NORMAL`;
- tracking action `PROMOTE_TO_TRACK_NORMAL`;
- priority reason `combined_discovery_handoff`;
- queue status `QUEUED`;
- source status `COMPLETE`;
- quality `CLEAN_DATA`;
- `last_checked_at` null.

These two queue rows are attributable durable residue even though `project_four_token_proof_zero_state()` does not count them. Leaving them `QUEUED` after moving their owning slots to `MANUAL_REVIEW` would be internally inconsistent. The reconciliation design therefore includes their exact terminal disposition.

## Why migration-056 provenance must not be backfilled

The production repair added migration 056 and a positive runtime witness for future `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` terminals. This historical execution predates that witness. Historical reconciliation must not fabricate a migration-056 provenance row or invoke shared Phase B as though the marker had existed at runtime.

## Why the old recover-orphan contract cannot be reused as-is

`operational_campaign_recovery.py` is pinned to execution `20260726T114155Z-95d9979a9302`, a different DB SHA, graph hash set and STOP_REQUESTED/STOPPING state. Its public contract also creates a terminal report row. Those assumptions do not match this execution.

The useful reusable owners are the underlying exact lifecycle owners, not the old execution-specific contract.

## First-cause contract

The preserved terminal cause is exactly:

`FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction`

Cleanup/reconciliation must preserve that cause on all newly terminalized ownership rows. No synthesized recovery cause may replace it.

## Exact reconciliation composition

No migration, report insertion, discovery, memory generation, source call, Scheduler runtime execution, new authorization or migration-056 provenance insertion is part of this cleanup.

The execution-scoped recovery will compose existing canonical owners in this order:

1. `reconcile_four_token_cycle_terminal(..., terminal_phase=None, run_status='FAILED')`
   - exact Cycle 1 only;
   - moves both historical slots `SELECTED -> MANUAL_REVIEW`;
   - terminalizes Cycle 1 with the preserved cause;
   - must record no migration-056 provenance.

2. `cleanup_campaign_supervision(..., terminal_status='FAILED')`
   - terminalizes campaign run and campaign with the preserved cause;
   - terminalizes supervision;
   - records cleanup/release timestamps;
   - releases the exact expired lease lock;
   - must find no active Scheduler/discovery work to cancel.

3. `reconcile_campaign_terminal(..., run_status='FAILED', lifecycle_started=False, factory_run_id=ed0fa279...)`
   - treats already-terminal campaign/run/Cycle 1 idempotently;
   - disposes queue ids 58 and 59 through the existing terminal owner because there is no terminal owned `WINDOW_15M`:
     `QUEUED -> SKIPPED`, `tracking_action -> MANUAL_REVIEW`, `priority_reason -> campaign_terminal:<preserved cause>`;
   - closes the exact factory run `RUNNING -> SAFE_STOPPED` with the preserved cause and finish timestamp;
   - performs no report insertion.

This sequence is deliberately chosen because running `reconcile_campaign_terminal()` before supervision cleanup would make `cleanup_campaign_supervision()` encounter already-terminal campaign/run ownership. Phase A first preserves the canonical slot/cycle owner; supervision cleanup second releases the lease; unified reconciliation last handles the two linked queues plus the factory-run close.

## Exact approved mutation set

Expected changed identities are exactly:

1. `printer_memory_factory_campaign_cycles`: historical Cycle 1.
2. `printer_memory_factory_campaign_token_slots`: historical slot 1.
3. `printer_memory_factory_campaign_token_slots`: historical slot 2.
4. `printer_memory_factory_campaign_runs`: historical campaign run.
5. `printer_memory_factory_campaigns`: historical campaign.
6. `printer_memory_factory_campaign_supervision`: historical supervision.
7. `printer_tracking_queue`: id 58.
8. `printer_tracking_queue`: id 59.
9. `printer_memory_factory_runs`: `ed0fa279-38e6-401b-8b34-0a9531a9c720`.
10. Filesystem: removal/release of the exact historical `campaign.lease.lock`.

That is nine database row identities across seven table groups, plus the one lease-lock release.

Explicitly unchanged:

- all 10 campaign Scheduler-work rows;
- Scheduler jobs 2011–2020;
- all discovery rows;
- campaign windows count remains zero;
- factory steps count remains zero;
- Cycle-2 attempts remain zero;
- migration ledger remains unchanged during disposable proof of the historical contract;
- migration-056 provenance remains absent for this execution;
- retrieval/financial locked tables remain byte-for-row identical;
- no rows are deleted.

## Fail-closed preconditions

Immediately before reconciliation the execution-scoped owner must prove:

- exact DB SHA `5e830af4...` for the historical 55-migration DB contract;
- exact identities/states/slot order/queue ids 58 and 59 and exact queue states above;
- zero windows/steps/Cycle-2 attempts/active discovery/proof supervision/active Scheduler work;
- jobs 2011–2020 terminal and unlocked;
- exact expired supervision lease and matching lease payload;
- no live Printer process;
- historical artifact SHA/evidence binding and preserved first cause;
- no migration-056 provenance for the execution.

Any drift fails closed. No repair-on-drift is permitted.

## Focused TDD contract

RED must prove at least:

- no execution-scoped historical reconciliation API exists yet;
- wrong DB SHA, identity, state, slot order, queue ids/state, live process/lease, active work, artifact binding or first-cause evidence fails closed;
- migration-056 provenance is never inserted;
- mutation outside the nine approved database identities fails the disposable row-diff proof.

GREEN must prove on disposable SQLite/filesystem fixtures:

- slots 1/2 -> `MANUAL_REVIEW`;
- Cycle 1/campaign run/campaign -> `TERMINAL_FAILED` with the preserved cause;
- supervision -> `TERMINAL`, terminal status `FAILED`, cleanup/release timestamps populated, exact lease file absent;
- queue ids 58/59 -> `SKIPPED`, action `MANUAL_REVIEW`, expected terminal priority reason;
- exact factory run -> `SAFE_STOPPED`, preserved stop reason, finished timestamp populated;
- terminal Scheduler work/jobs unchanged;
- windows/steps/Cycle-2 attempts remain zero;
- migration-056 provenance remains absent for this execution;
- locked retrieval/financial row hashes unchanged;
- database integrity/FK clean;
- repeat invocation is idempotent or safely no-op with zero additional mutation.

## Bounded proof

The first proof must use a disposable copy of the exact historical database plus disposable artifact/lease paths. It must bind the source SHA, execute the recovery, and compare table-level rows before/after to prove no mutation outside the nine approved database identities.

Only after that proof and implementation closeout pass may authoritative Mac-local reconciliation be considered. Immediately before authoritative mutation, repeat the complete read-only evidence contract and create a fresh byte-identical pre-reconciliation backup plus restore rehearsal.

## Money-usefulness contribution

This lane removes abandoned durable ownership that otherwise prevents trustworthy bounded memory-growth operations. It improves recoverability and evidence integrity; it does not generate memories, decisions, positions or PnL.

## What remains locked

No fresh four-token authorization, operational proof, six-token widening, 12h/24h activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events/audits or PnL is unlocked by this repair.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Authoritative mutation still requires a final Mac-local recheck immediately before execution.
2. Migration 056 is not part of this historical 55-migration DB identity and must not be applied merely to perform cleanup.
3. The two queue rows were missed by the earlier zero-state-domain audit because that projection does not count `printer_tracking_queue`; the focused proof must therefore assert their disposition explicitly.
4. The historical terminal truth remains `RECONSTRUCTED` with unknown unattributable terminal time; cleanup must not rewrite history to imply successful original closeout.
5. Any DB mutation before the authoritative reconciliation invalidates the pinned SHA and requires a new audit/design decision rather than automatic rebasing.

## Safest next step

Focused RED -> minimal execution-scoped implementation -> focused GREEN -> disposable exact-diff proof -> independent closeout. Authoritative DB remains untouched until those gates pass.

# Printer V1 V2-9.8B — Historical Execution Reconciliation Audit & Design

## Verdict

`V2_9_8B_HISTORICAL_EXECUTION_RECONCILIATION_AUDIT_DESIGN_PASS_READY_FOR_LOCAL_EVIDENCE_BINDING_AND_FOCUSED_TDD`

## Lane identity

- Starting repair closeout: `1b5a8cdf0dad74b8fa4730d090abfc8d6cd184a1`
- Historical execution: `20260814T172224Z-490856f405bf`
- Historical factory run: `ed0fa279-38e6-401b-8b34-0a9531a9c720`
- Preserved pre-reconciliation DB SHA from the completed audit: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`
- Historical schema head: `055_pre_admission_discovery_attempt_ownership.sql`
- Branch: `agent/v2-9-8b-historical-execution-reconciliation`

This lane does not authorize a fresh Printer run or any financial/retrieval capability.

## Audit confirmation

The committed zero-state audit proves that the historical execution owns the abandoned graph and that, at audit time, no live Printer process, Scheduler job lock, proof supervision, or valid campaign lease remained. The graph consisted of campaign RUNNING, campaign-run RUNNING, Cycle 1 PLANNED, supervision ACTIVE, factory run RUNNING, two SELECTED slots, zero campaign windows, zero factory steps, and zero Cycle-2 pre-admission attempts.

The production repair added migration 056 and a positive runtime witness for future `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` terminals. The historical execution predates that witness and **must not receive a fabricated migration-056 provenance row**.

## Why the existing recover-orphan owner cannot be reused as-is

`operational_campaign_recovery.py` is hard-pinned to execution `20260726T114155Z-95d9979a9302`, a different DB SHA, different graph hashes and a different STOP_REQUESTED / STOPPING state. It also writes a new terminal report row. Those assumptions do not match this historical execution.

The existing shared terminal Phase B also cannot be invoked against the historical graph because the exact migration-056 provenance was never recorded at runtime. Backfilling it would erase the distinction between runtime evidence and later forensic reconstruction.

## Historical evidence contract

Before any authoritative mutation, a Mac-local read-only evidence pass must re-prove all of the following against the exact current database and artifact root:

1. DB SHA is still exactly `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`.
2. Schema ledger remains exactly 55 migrations ending at migration 055.
3. `PRAGMA integrity_check` is `ok` and `foreign_key_check` is empty.
4. No SQLite sidecars exist.
5. Exact campaign/run/cycle/supervision/factory identities match the historical execution.
6. States remain campaign RUNNING, run RUNNING, Cycle 1 PLANNED, supervision ACTIVE, factory run RUNNING.
7. Exactly two Cycle-1 slots exist in preserved slot order:
   - slot 1: `yUmeQo96g6MurikjHiMg7u23X5yQXJ9SQpoJPcbpump`
   - slot 2: `CAGtwKrcnwgLABdg5o16oMczxUV6i1pj973K9XWQpump`
8. The two slots' `tracking_queue_id` values are reported explicitly. The mutation plan is not frozen until these are known.
9. Zero Cycle-1 campaign windows, zero factory steps, zero Cycle-2 pre-admission attempts.
10. Ten campaign Scheduler-work rows remain terminal and canonical; Scheduler jobs 2011–2020 remain terminal and unlocked.
11. No active discovery work, active Scheduler jobs, proof supervision, or live Printer process exists.
12. Campaign lease is expired; the lease-lock file is not held by a live process and its ownership payload matches the exact supervision/campaign/run/owner identities.
13. Preserved operator artifacts exist and are bound to the same execution. Record SHA256 for at least `application-marker.json`, `git-provenance-manifest.json`, `wrapper-terminal.json`, `child-terminal.json`, `child-stderr.txt`, and `terminal-summary.json` when present.
14. Artifact evidence preserves the historical failure sequence and does not contradict the committed first-cause evidence.

Any drift blocks reconciliation. Do not "repair the drift" inside this lane.

## First-cause contract

The reconciliation cause remains the historical controlling failure recorded by the audit:

`FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh transaction`

A local artifact check must confirm that this remains compatible with the preserved wrapper/child evidence. If the immutable artifacts prove a more precise earlier first cause, stop and amend the design before mutation; do not silently substitute a cleanup reason.

## Exact mutation design

No migration and no migration-056 provenance backfill are part of historical cleanup.

The intended composition is:

1. use `reconcile_four_token_cycle_terminal()` Phase A with `terminal_phase=None` to terminalize the exact historical Cycle 1 and its two slots through the existing ownership owners;
2. use `cleanup_campaign_supervision()` with the historical first cause to terminalize remaining campaign/run supervision ownership and release the exact lease;
3. close the exact historical factory run through a narrowly owned factory-run terminal step only after proving it cannot change any unrelated row;
4. prove zero active campaign ownership, zero active/locked Scheduler work, integrity/FK clean, and retrieval/financial table hashes unchanged.

Do **not** call shared Phase B and do **not** insert historical provenance into migration 056.

### Tracking-queue guard

`reconcile_campaign_terminal()` is not automatically approved as step 3 because it can also mutate linked tracking-queue rows. If either historical slot has a non-null `tracking_queue_id`, this lane must enumerate the exact queue state and decide whether that mutation is part of the evidence-backed closeout. If both are null, a narrowly bounded use/refactor of the existing terminal owner may be acceptable.

### Mutation-count correction

The prior audit described "6 row updates + lease-lock release" while its own enumeration includes two slots plus cycle, campaign run, campaign, supervision and factory run. That is **7 row identities across 6 table groups**, plus lease-lock release. This design uses the explicit row identities, not the shorthand count.

No report insertion is required by this cleanup design. Historical evidence already exists in committed audit documentation and immutable operator artifacts; adding a new report row would widen the audited mutation set.

## Focused TDD contract

RED must prove at least:

- exact historical-shaped one-cycle/zero-attempt residue is rejected without the dedicated reconciliation path;
- any DB SHA, identity, slot order, active-work, lease, artifact-binding or state drift fails closed;
- migration-056 provenance is never inserted by historical reconciliation;
- unexpected tracking-queue linkage blocks until explicitly designed;
- no source, discovery, memory, Scheduler runtime or financial/retrieval work is created.

GREEN must prove on disposable SQLite:

- exact two slots become `MANUAL_REVIEW`;
- Cycle 1, campaign run and campaign become terminal with the preserved cause;
- supervision becomes terminal with cleanup/release timestamps and lease file removed;
- factory run becomes `SAFE_STOPPED` with preserved cause and finish timestamp;
- all existing terminal Scheduler work/jobs remain unchanged;
- zero windows/steps/attempts remain zero;
- migration-056 provenance remains absent for the historical execution;
- locked retrieval/financial table counts and row hashes are unchanged;
- database integrity/FK remain clean;
- repeat invocation is idempotent or fails safely without additional mutation.

## Bounded proof

The first proof must use a disposable copy only. It must bind the exact pre-copy SHA, run the historical reconciliation, then compare table-level row hashes before/after and reject any mutation outside the approved execution-scoped set.

Only after that proof passes may the authoritative Mac-local execution be considered. Immediately before authoritative mutation, re-run the complete read-only evidence contract. Create a fresh byte-identical pre-reconciliation backup and verify restore before mutation.

## Money-usefulness contribution

This lane removes abandoned durable ownership that otherwise prevents trustworthy bounded memory-growth operations. It improves operational recoverability and evidence integrity; it does not generate memory, trading decisions, positions or PnL.

## What remains locked

No fresh four-token authorization, new operational proof, six-token widening, 12h/24h activation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events/audits or PnL is unlocked by this design.

## Functionality Risks / Setbacks / Efficiency Blockers

1. Current Mac-local DB/process/artifact state is not observable through GitHub and must be revalidated locally.
2. Tracking-queue linkage is not recorded in the prior audit and can change the exact mutation set.
3. The historical execution cannot legitimately use the new migration-056 runtime provenance contract.
4. Any authoritative schema migration before this exact cleanup changes the pinned DB SHA and invalidates this design's current evidence binding.
5. The historical first-cause string must remain consistent with immutable artifacts before mutation.

## Safest next step

Run the exact Mac-local read-only evidence collection. If all facts match and tracking-queue/artifact evidence is unambiguous, freeze those facts into focused RED tests and the execution-scoped recovery implementation. No authoritative mutation before disposable proof passes.

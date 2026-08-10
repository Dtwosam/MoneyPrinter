# Printer V1 V2-9.8B Post-DTW100 WINDOW_1H Checkpoint 3 — Remaining 45-Minute Collection Audit

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_3_AUDIT_BLOCKED_ACTIVE_COLLECTION_STATE_AND_ACCOUNTING_SYNC_REPAIR_REQUIRED`

Checkpoint 3 starts from the exact Checkpoint-2 state: each continuing token has an exact `WINDOW_1H` campaign successor, token state `WINDOW_1H_CONTINUING`, and cadence-derived Central Scheduler jobs durably owned by that exact successor.

The governed snapshot collection machinery itself is reusable and healthy: continuation snapshot steps use the same exact-pair snapshot owner, Source Governor request boundary, response/failure provenance, snapshot persistence, and hard budget checks as the proven 15m path.

Three synchronization gaps block Checkpoint 3 completion:

1. stage-scoped campaign Scheduler ownership rows are projected at enqueue as `PENDING` but are not resynchronized when their real Scheduler jobs become `RUNNING`, `SUCCEEDED`, `FAILED`, or `CANCELLED`;
2. the exact `WINDOW_1H` campaign window remains `PLANNED` while continuation observations are actively being collected, and collection failure/cancellation can leave it nonterminal;
3. the run-loop lifecycle-reservation observer emits reservation identities for 15m `SNAPSHOT` / `WINDOW_CLOSE` only, while governed `CONTINUATION_SNAPSHOT` and `CONTINUATION_CLOSE` work also consumes one lifecycle transport each.

These are lifecycle/accounting truth gaps around working collection, not a reason to duplicate or rewrite source adapters.

## Baseline

- Repository: `Dtwosam/MoneyPrinter`
- Checkpoint-2 exact closeout HEAD: `7e489ad8665fce4c0fcfe04e98d5c2d215d6253e`
- Checkpoint-3 branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint3-remaining-45m-collection`
- Branch created exactly from the Checkpoint-2 closeout HEAD.

No provider/RPC call, Scheduler runtime, authoritative DB mutation, authorization creation, wrapper execution, real memory collection, retrieval, paper decision, position, trade, audit, PnL, wallet, signing, or real-fund action occurred in this audit.

## Healthy and reusable collection path

### Central Scheduler execution

The main factory loop selects the earliest due `PENDING` run-step, claims its exact `scheduler_job_id` with `claim_due_job()`, marks the factory run-step `RUNNING`, executes the approved step owner, then calls `complete_job()` or `fail_job()` with zero retries. Token-local failure cancels only that token's pending work; global integrity/budget failure safely stops the run.

There is no private 1h loop.

### Exact-pair governed source collection

`_execute_snapshot()` is shared by 15m and `CONTINUATION_SNAPSHOT` work. It:

- uses the step's exact token mint and pair address;
- builds the existing DexScreener exact-pair governed request;
- executes through Source Governor;
- validates exact pair identity;
- records source request/response/failure ids;
- permits only the existing one-shot governed GeckoTerminal fallback for the approved transient primary-failure classes;
- persists no snapshot when governed evidence fails or mismatches;
- persists the snapshot through the existing shared snapshot owner when evidence is valid.

The uploaded Source Governor rules likewise require every request to pass Source Governor, durable request/response/failure rows, exact source attribution, and no bypass.

### Hard request and Scheduler ceilings

`_enforce_budgets_before_step()` counts `CONTINUATION_SNAPSHOT` and `CONTINUATION_CLOSE` as one projected governed request each. `_continuation_expected_snapshots()` derives 1h counts from the authoritative cadence policy. The current two-token/first-hour ceiling machinery therefore already accounts for continuation request and Scheduler-row capacity.

### Two-token service order

Pending work is ordered by `scheduled_for, id`. Checkpoint 2 creates both tokens from the same 15m-close anchored cadence. A token whose job is not due is not eligible service. At shared due points the deterministic id tie-break gives one service then the other; the loop does not spin privately on one token. Token-local source failure cancels only that token's remaining work and leaves the peer's work available.

### Continuity and missing-data honesty

The shared 1h cadence policy defines gap and minimum-snapshot rules; missing snapshots are reported rather than interpolated. A failed governed continuation observation therefore cannot silently become clean evidence.

## Blocker 1 — Scheduler ownership state does not follow Scheduler truth

Checkpoint 2 now creates one exact `V2_STAGE_SCOPED / WINDOW_LIFECYCLE` campaign ownership row for every continuation Scheduler job.

`project_campaign_scheduler_job()` already knows how to map real Scheduler states into campaign `work_state` and, on a repeat exact projection, synchronize the existing row's mutable state while preserving immutable identity.

However, the factory execution loop does not call that owner after:

- successful claim;
- successful completion;
- failure;
- token-local cancellation;
- global cancellation.

Therefore a job can be `RUNNING`, `SUCCEEDED`, `FAILED`, or `CANCELLED` while its exact campaign work row still says `PENDING`.

This violates the stage-scoped ownership design requirement that campaign reporting observe the real Scheduler enqueue/claim/terminal lifecycle rather than infer it later.

## Blocker 2 — active WINDOW_1H graph remains PLANNED

Checkpoint 1 correctly creates `WINDOW_1H` in `PLANNED` state. Checkpoint 2 correctly leaves it `PLANNED` before any continuation job has executed.

But when the first owned `CONTINUATION_SNAPSHOT` is claimed/collected, no current owner moves the campaign window to `COLLECTING`. The later close binding helper can walk `PLANNED -> COLLECTING -> CLOSE_PENDING -> AUDITING` retroactively, but that does not make active collection state truthful while the 45-minute lifecycle is actually running.

Likewise, if a continuation observation hard-fails and the token's remaining work is cancelled, the exact 1h campaign window can remain nonterminal even though that lifecycle can no longer complete.

Checkpoint 3 must establish truthful active/failed collection state before the close boundary is audited.

## Blocker 3 — continuation lifecycle reservation identities are omitted

The hard budget gate correctly counts continuation source requests. Separately, the lifecycle operation observer constructs durable `LIFECYCLE_RESERVATION` identities only when `step_kind` is `SNAPSHOT` or `WINDOW_CLOSE`.

`CONTINUATION_SNAPSHOT` and `CONTINUATION_CLOSE` each execute one governed snapshot request, but currently emit no corresponding lifecycle reservation identity. This creates a six-unit accounting observability gap for first-hour operation even though the hard request ceiling itself is correct.

The existing reservation machinery can be reused; no new accounting system is required.

## Required repair direction

### Scheduler state synchronization

Add one narrow factory helper that:

1. looks up an existing stage-scoped campaign Scheduler ownership row by exact `scheduler_job_id`;
2. if none exists, does nothing so historical non-campaign paths remain compatible;
3. if one exists, calls the existing `project_campaign_scheduler_job()` with the row's immutable campaign/window/factory identity and exact Scheduler job id;
4. lets the canonical helper derive current Scheduler state and synchronize `work_state`;
5. fails closed on any ownership mismatch.

Invoke it after claim and after every complete/fail/cancel operation affecting owned continuation work.

### WINDOW_1H collection-state synchronization

For an exactly-owned `CONTINUATION_SNAPSHOT`:

- after successful Scheduler claim, move its exact campaign window `PLANNED -> COLLECTING` through the existing campaign state transition owner;
- repeat claims while already `COLLECTING` are idempotent/no-op at this layer;
- if collection fails and the token's continuation becomes terminally unusable, terminalize the exact active 1h campaign window `BLOCKED` with a durable first cause rather than leaving it `PLANNED/COLLECTING`;
- operator/global cancellation uses `CANCELLED`, not a fake clean/dirty outcome.

Do not perform `CLOSE_PENDING` or 1h close semantics here; Checkpoint 4 owns the close boundary.

### Lifecycle reservation reuse

Use the existing `_projected_requests_for_step()` result to emit lifecycle reservation records for:

- `SNAPSHOT`;
- `WINDOW_CLOSE`;
- `CONTINUATION_SNAPSHOT`;
- `CONTINUATION_CLOSE`.

For continuation work the count remains one. No request budget is increased.

## Minimum focused proof

Offline proof must establish:

1. Checkpoint-2 initialization still creates exact owned continuation jobs;
2. claiming an owned continuation job changes exact campaign work `PENDING -> RUNNING`;
3. the first continuation claim moves the exact `WINDOW_1H` from `PLANNED -> COLLECTING`;
4. successful exact-pair governed fixture collection persists the correct token/pair snapshot and Source Governor request/response provenance;
5. completing the job changes campaign work to `SUCCEEDED`;
6. failed source evidence changes exact work to `FAILED`, cancels the token's remaining continuation jobs/work rows, and terminalizes only that token's 1h window without corrupting the peer;
7. global cancellation synchronizes owned pending rows and windows to cancellation-safe terminal state;
8. continuation snapshot/close operations emit the correct one lifecycle-reservation identity each;
9. no retry/restart/successor is created;
10. Checkpoints 1-2 and current first-hour operational tests remain green.

## Money-usefulness contribution

Printer's 1h memory must describe evidence that was actually collected under one truthful lifecycle. Synchronizing job, window, and accounting state prevents orphan work, false-active/false-pending labels, and unaccounted source observations from contaminating later trajectory interpretation.

## What this checkpoint improves

When repaired, the active 45-minute collection path will truthfully compose:

`exact WINDOW_1H owner -> exact Scheduler job -> governed exact-pair source attempt -> exact snapshot -> exact Scheduler terminal state -> exact campaign work state`

while preserving token-local failure isolation.

## What this checkpoint still does not unlock

- no real first-hour run;
- no one-use authorization/wrapper;
- no provider/RPC source execution against live endpoints;
- no authoritative DB mutation;
- no 1h close-boundary proof — Checkpoint 4;
- no final genuine 1h clean-memory proof — Checkpoints 5-6;
- no 4h activation;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

- Do not create a second Scheduler-state machine; the canonical projection already maps real Scheduler state.
- Do not copy snapshot/source logic into a 1h-specific collector.
- Window terminalization must not convert source failure into DIRTY/CLEAN memory; it is an ownership/lifecycle BLOCK/CANCEL state only.
- Reservation observability must not raise request ceilings or add source calls.
- Close-state transitions remain out of scope until Checkpoint 4.

## Next action

Design the narrow active collection state/accounting synchronization repair. Checkpoint 4 remains blocked until implementation, focused proof, and Checkpoint-3 closeout pass.
